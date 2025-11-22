"""Tests for LIFXEffect base class."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.color import HSBK
from lifx.const import KELVIN_NEUTRAL
from lifx.effects.base import LIFXEffect
from lifx.effects.const import DEFAULT_BRIGHTNESS


class ConcreteEffect(LIFXEffect):
    """Concrete implementation for testing abstract base class."""

    @property
    def name(self) -> str:
        """Return the name of the effect."""
        return "test"

    async def async_play(self) -> None:
        """Minimal implementation for testing."""
        pass


@pytest.fixture
def effect():
    """Create a concrete effect instance for testing."""
    return ConcreteEffect(power_on=True)


@pytest.fixture
def mock_light():
    """Create a mock light device."""
    light = MagicMock()
    light.serial = "d073d5123456"
    return light


def test_effect_initialization(effect):
    """Test effect initialization."""
    assert effect.power_on is True
    assert effect.conductor is None
    assert effect.participants == []


def test_effect_initialization_power_off():
    """Test effect initialization with power_on=False."""
    effect = ConcreteEffect(power_on=False)
    assert effect.power_on is False


def test_inherit_prestate_default(effect):
    """Test default inherit_prestate returns False."""
    other_effect = ConcreteEffect()
    assert effect.inherit_prestate(other_effect) is False


def test_effect_repr(effect):
    """Test effect string representation."""
    repr_str = repr(effect)
    assert "ConcreteEffect" in repr_str
    assert "power_on=True" in repr_str


@pytest.mark.asyncio
async def test_fetch_light_color_from_device(effect, mock_light):
    """Test fetching color from device."""
    # Setup device color
    device_color = HSBK(hue=240, saturation=0.9, brightness=0.7, kelvin=4000)
    mock_light.get_color = AsyncMock(return_value=(device_color, True, "Test Light"))

    # Fetch color
    result = await effect.fetch_light_color(mock_light)

    # Should fetch from device
    assert result == device_color
    mock_light.get_color.assert_called_once()


@pytest.mark.asyncio
async def test_fetch_light_color_brightness_boost(effect, mock_light):
    """Test brightness boost when color is too dim."""
    # Setup dim color from device
    dim_color = HSBK(hue=180, saturation=1.0, brightness=0.05, kelvin=3500)
    mock_light.get_color = AsyncMock(return_value=(dim_color, True, "Test Light"))

    # Fetch color with default fallback
    result = await effect.fetch_light_color(mock_light)

    # Brightness should be boosted to default
    assert result.hue == dim_color.hue
    assert result.saturation == dim_color.saturation
    assert result.brightness == DEFAULT_BRIGHTNESS
    assert result.kelvin == dim_color.kelvin


@pytest.mark.asyncio
async def test_fetch_light_color_custom_fallback(effect, mock_light):
    """Test brightness boost with custom fallback brightness."""
    # Setup dim color from device
    dim_color = HSBK(hue=90, saturation=0.8, brightness=0.02, kelvin=2700)
    mock_light.get_color = AsyncMock(return_value=(dim_color, True, "Test Light"))

    # Fetch color with custom fallback
    result = await effect.fetch_light_color(
        mock_light, fallback_brightness=0.5, min_brightness=0.1
    )

    # Brightness should be boosted to custom fallback
    assert result.brightness == 0.5


@pytest.mark.asyncio
async def test_fetch_light_color_custom_min_threshold(effect, mock_light):
    """Test custom minimum brightness threshold."""
    # Setup color just below custom threshold from device
    color = HSBK(hue=45, saturation=0.7, brightness=0.15, kelvin=3000)
    mock_light.get_color = AsyncMock(return_value=(color, True, "Test Light"))

    # Fetch with higher minimum threshold
    result = await effect.fetch_light_color(
        mock_light, fallback_brightness=0.6, min_brightness=0.2
    )

    # Should be boosted because 0.15 < 0.2
    assert result.brightness == 0.6


@pytest.mark.asyncio
async def test_fetch_light_color_exception_handling(effect, mock_light):
    """Test fallback when color fetch raises exception."""
    # Setup mock to raise exception
    mock_light.get_color = AsyncMock(side_effect=Exception("Network error"))

    # Fetch color should return fallback
    result = await effect.fetch_light_color(mock_light)

    # Should return fallback color
    assert isinstance(result, HSBK)
    assert result.saturation == 1.0
    assert result.brightness == DEFAULT_BRIGHTNESS
    assert result.kelvin == KELVIN_NEUTRAL
    # Hue should be random (0-360)
    assert 0 <= result.hue <= 360


@pytest.mark.asyncio
async def test_fetch_light_color_exception_with_custom_brightness(effect, mock_light):
    """Test fallback with custom brightness when exception occurs."""
    # Setup mock to raise exception
    mock_light.get_color = AsyncMock(side_effect=Exception("Timeout"))

    # Fetch color with custom fallback brightness
    result = await effect.fetch_light_color(mock_light, fallback_brightness=0.3)

    # Fallback should use custom brightness
    assert result.brightness == 0.3


def test_get_fallback_color_default(effect):
    """Test _get_fallback_color with default brightness."""
    result = effect._get_fallback_color()

    # Should return valid HSBK
    assert isinstance(result, HSBK)
    assert 0 <= result.hue <= 360
    assert result.saturation == 1.0
    assert result.brightness == DEFAULT_BRIGHTNESS
    assert result.kelvin == KELVIN_NEUTRAL


def test_get_fallback_color_custom_brightness(effect):
    """Test _get_fallback_color with custom brightness."""
    result = effect._get_fallback_color(brightness=0.4)

    # Should use custom brightness
    assert result.brightness == 0.4


def test_get_fallback_color_randomness(effect):
    """Test that fallback color has random hue."""
    # Generate multiple fallback colors
    colors = [effect._get_fallback_color() for _ in range(10)]

    # Should have variety in hues (not all the same)
    unique_hues = set(c.hue for c in colors)
    assert len(unique_hues) > 1  # At least some variation


@pytest.mark.asyncio
async def test_from_poweroff_hsbk_returns_random(effect, mock_light):
    """Test from_poweroff_hsbk returns random hue with zero brightness."""
    result = await effect.from_poweroff_hsbk(mock_light)

    # Should return valid startup color
    assert isinstance(result, HSBK)
    assert 0 <= result.hue <= 360
    assert result.saturation == 1.0
    assert result.brightness == 0.0
    assert result.kelvin == KELVIN_NEUTRAL


@pytest.mark.asyncio
async def test_async_perform_sets_participants(effect, mock_light):
    """Test async_perform sets participants."""
    # Setup required async methods
    mock_light.get_power = AsyncMock(return_value=True)
    mock_light.set_color = AsyncMock()
    mock_light.set_power = AsyncMock()

    participants = [mock_light]

    await effect.async_perform(participants)

    assert effect.participants == participants


@pytest.mark.asyncio
async def test_async_perform_without_power_on(mock_light):
    """Test async_perform without powering on lights."""
    effect = ConcreteEffect(power_on=False)
    mock_light.get_power = AsyncMock(return_value=True)

    await effect.async_perform([mock_light])

    # Should not check power or power on
    assert not mock_light.get_power.called


@pytest.mark.asyncio
async def test_async_perform_powers_on_if_off(mock_light):
    """Test async_perform powers on lights that are off."""
    effect = ConcreteEffect(power_on=True)
    mock_light.get_power = AsyncMock(return_value=False)
    mock_light.set_color = AsyncMock()
    mock_light.set_power = AsyncMock()

    await effect.async_perform([mock_light])

    # Should power on the light
    mock_light.get_power.assert_called_once()
    mock_light.set_color.assert_called_once()
    mock_light.set_power.assert_called_once_with(True, duration=0.3)


@pytest.mark.asyncio
async def test_async_perform_skips_already_on_lights(mock_light):
    """Test async_perform skips lights that are already on."""
    effect = ConcreteEffect(power_on=True)
    mock_light.get_power = AsyncMock(return_value=True)
    mock_light.set_power = AsyncMock()

    await effect.async_perform([mock_light])

    # Should check power but not set it
    mock_light.get_power.assert_called_once()
    assert not mock_light.set_power.called


@pytest.mark.asyncio
async def test_is_light_compatible_default_no_color_required(effect, mock_light):
    """Test is_light_compatible when effect doesn't require color."""
    # Effect doesn't require color, all lights are compatible
    is_compatible = await effect.is_light_compatible(mock_light)
    assert is_compatible is True


@pytest.mark.asyncio
async def test_is_light_compatible_color_required_with_color_support():
    """Test is_light_compatible when effect requires color and light supports it."""

    class ColorEffect(ConcreteEffect):
        async def is_light_compatible(self, light) -> bool:
            """Require color capability."""
            if light.capabilities is None:
                await light._ensure_capabilities()
            return light.capabilities.has_color if light.capabilities else False

    effect = ColorEffect()

    # Mock light with color support
    light = MagicMock()
    light.serial = "d073d5color"
    light.capabilities = MagicMock()
    light.capabilities.has_color = True

    is_compatible = await effect.is_light_compatible(light)
    assert is_compatible is True


@pytest.mark.asyncio
async def test_is_light_compatible_color_required_without_color_support():
    """Test is_light_compatible when effect requires color."""

    class ColorEffect(ConcreteEffect):
        async def is_light_compatible(self, light) -> bool:
            """Require color capability."""
            if light.capabilities is None:
                await light._ensure_capabilities()
            return light.capabilities.has_color if light.capabilities else False

    effect = ColorEffect()

    # Mock white light without color support
    light = MagicMock()
    light.serial = "d073d5white"
    light.capabilities = MagicMock()
    light.capabilities.has_color = False

    is_compatible = await effect.is_light_compatible(light)
    assert is_compatible is False


@pytest.mark.asyncio
async def test_is_light_compatible_loads_capabilities():
    """Test is_light_compatible loads capabilities if not cached."""

    class ColorEffect(ConcreteEffect):
        async def is_light_compatible(self, light) -> bool:
            """Require color capability."""
            if light.capabilities is None:
                await light._ensure_capabilities()
            return light.capabilities.has_color if light.capabilities else False

    effect = ColorEffect()

    # Mock light without cached capabilities
    light = MagicMock()
    light.serial = "d073d5nocaps"
    light.capabilities = None
    light._ensure_capabilities = AsyncMock()

    # After loading, set capabilities
    async def mock_ensure_capabilities():
        light.capabilities = MagicMock()
        light.capabilities.has_color = True

    light._ensure_capabilities.side_effect = mock_ensure_capabilities

    is_compatible = await effect.is_light_compatible(light)

    # Should have loaded capabilities
    light._ensure_capabilities.assert_called_once()
    assert is_compatible is True


@pytest.mark.asyncio
async def test_is_light_compatible_custom_implementation():
    """Test custom is_light_compatible implementation."""

    class CustomEffect(ConcreteEffect):
        """Effect with custom compatibility logic."""

        async def is_light_compatible(self, light) -> bool:
            """Require multizone capability."""
            if light.capabilities is None:
                await light._ensure_capabilities()
            return light.capabilities.has_multizone if light.capabilities else False

    effect = CustomEffect()

    # Mock multizone light
    multizone_light = MagicMock()
    multizone_light.serial = "d073d5multizone"
    multizone_light.capabilities = MagicMock()
    multizone_light.capabilities.has_multizone = True

    # Mock regular light
    regular_light = MagicMock()
    regular_light.serial = "d073d5regular"
    regular_light.capabilities = MagicMock()
    regular_light.capabilities.has_multizone = False

    # Only multizone light should be compatible
    assert await effect.is_light_compatible(multizone_light) is True
    assert await effect.is_light_compatible(regular_light) is False
