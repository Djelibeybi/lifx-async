"""Tests for EffectSpin (color migration)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.color import HSBK
from lifx.effects.base import LIFXEffect
from lifx.effects.frame_effect import FrameContext, FrameEffect
from lifx.effects.spin import EffectSpin
from lifx.theme.library import ThemeLibrary
from lifx.theme.theme import Theme

# ---------------------------------------------------------------------------
# Default parameters
# ---------------------------------------------------------------------------


def test_spin_default_parameters() -> None:
    """Test EffectSpin with default parameters."""
    effect = EffectSpin()

    assert effect.name == "spin"
    assert effect.speed == 10.0
    assert effect.bulb_offset == 5.0
    assert effect.brightness == 0.8
    assert effect.kelvin == 3500
    assert effect.zones_per_bulb == 1
    assert effect.power_on is True
    assert effect.fps == 20.0
    assert effect.duration is None


def test_spin_default_theme_is_exciting() -> None:
    """Test EffectSpin uses 'exciting' theme when no theme is provided."""
    effect = EffectSpin()
    exciting = ThemeLibrary.get("exciting")

    assert len(effect.theme) == len(exciting)
    for a, b in zip(effect.theme, exciting):
        assert a.hue == b.hue
        assert a.saturation == b.saturation
        assert a.brightness == b.brightness
        assert a.kelvin == b.kelvin


# ---------------------------------------------------------------------------
# Custom parameters
# ---------------------------------------------------------------------------


def test_spin_custom_parameters() -> None:
    """Test EffectSpin with custom parameters."""
    custom_theme = Theme(
        [
            HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500),
            HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=3500),
            HSBK(hue=240, saturation=1.0, brightness=1.0, kelvin=3500),
        ]
    )
    effect = EffectSpin(
        speed=5.0,
        theme=custom_theme,
        bulb_offset=10.0,
        brightness=0.6,
        kelvin=5000,
        zones_per_bulb=3,
        power_on=False,
    )

    assert effect.speed == 5.0
    assert effect.theme is custom_theme
    assert effect.bulb_offset == 10.0
    assert effect.brightness == 0.6
    assert effect.kelvin == 5000
    assert effect.zones_per_bulb == 3
    assert effect.power_on is False


def test_spin_custom_theme_used_in_frame() -> None:
    """Test that a custom theme's colors appear in generated frames."""
    custom_theme = Theme(
        [
            HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500),
            HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=3500),
        ]
    )
    effect = EffectSpin(theme=custom_theme, bulb_offset=0.0, brightness=0.8)
    ctx = FrameContext(
        elapsed_s=0.0,
        device_index=0,
        pixel_count=16,
        canvas_width=16,
        canvas_height=1,
    )
    colors = effect.generate_frame(ctx)

    # With bulb_offset=0 and elapsed_s=0, hues should derive from the
    # two-color theme via Oklab interpolation -- all hues should be
    # somewhere in the 0-120 range (or wrapped around via Oklab).
    assert len(colors) == 16
    for c in colors:
        assert 0.0 <= c.brightness <= 1.0


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_spin_invalid_speed() -> None:
    """Test EffectSpin with invalid speed raises ValueError."""
    with pytest.raises(ValueError, match="Speed must be"):
        EffectSpin(speed=0)

    with pytest.raises(ValueError, match="Speed must be"):
        EffectSpin(speed=-1.0)


def test_spin_invalid_bulb_offset() -> None:
    """Test EffectSpin with invalid bulb_offset raises ValueError."""
    with pytest.raises(ValueError, match="bulb_offset must be"):
        EffectSpin(bulb_offset=-1.0)

    with pytest.raises(ValueError, match="bulb_offset must be"):
        EffectSpin(bulb_offset=361.0)


def test_spin_invalid_brightness() -> None:
    """Test EffectSpin with invalid brightness raises ValueError."""
    with pytest.raises(ValueError, match="Brightness must be"):
        EffectSpin(brightness=1.5)

    with pytest.raises(ValueError, match="Brightness must be"):
        EffectSpin(brightness=-0.1)


def test_spin_invalid_kelvin() -> None:
    """Test EffectSpin with invalid kelvin raises ValueError."""
    with pytest.raises(ValueError, match="Kelvin must be"):
        EffectSpin(kelvin=1000)

    with pytest.raises(ValueError, match="Kelvin must be"):
        EffectSpin(kelvin=10000)


def test_spin_invalid_zones_per_bulb() -> None:
    """Test EffectSpin with invalid zones_per_bulb raises ValueError."""
    with pytest.raises(ValueError, match="zones_per_bulb must be"):
        EffectSpin(zones_per_bulb=0)

    with pytest.raises(ValueError, match="zones_per_bulb must be"):
        EffectSpin(zones_per_bulb=-1)


# ---------------------------------------------------------------------------
# Frame generation
# ---------------------------------------------------------------------------


class TestSpinGenerateFrame:
    """Tests for EffectSpin.generate_frame()."""

    @pytest.mark.parametrize("pixel_count", [1, 8, 16, 82])
    def test_frame_length(self, pixel_count: int) -> None:
        """Test correct number of colors for various pixel counts."""
        effect = EffectSpin()
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=pixel_count,
            canvas_width=pixel_count,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        assert len(colors) == pixel_count

    def test_valid_hsbk_values(self) -> None:
        """Test all generated HSBK values are in valid ranges."""
        effect = EffectSpin()
        ctx = FrameContext(
            elapsed_s=2.5,
            device_index=0,
            pixel_count=32,
            canvas_width=32,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        for color in colors:
            assert 0 <= color.hue <= 360
            assert 0.0 <= color.saturation <= 1.0
            assert 0.0 <= color.brightness <= 1.0
            assert 1500 <= color.kelvin <= 9000

    def test_brightness_matches_configured(self) -> None:
        """Test pixel brightnesses match the configured brightness."""
        effect = EffectSpin(brightness=0.6)
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=8,
            canvas_width=8,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        for color in colors:
            assert color.brightness == 0.6

    def test_kelvin_matches_configured(self) -> None:
        """Test kelvin values match configured kelvin."""
        effect = EffectSpin(kelvin=5000)
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=8,
            canvas_width=8,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        for color in colors:
            assert color.kelvin == 5000

    def test_frame_changes_over_time(self) -> None:
        """Test different elapsed_s produce different frames."""
        effect = EffectSpin()
        ctx1 = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=8,
            canvas_width=8,
            canvas_height=1,
        )
        ctx2 = FrameContext(
            elapsed_s=3.0,
            device_index=0,
            pixel_count=8,
            canvas_width=8,
            canvas_height=1,
        )
        colors1 = effect.generate_frame(ctx1)
        colors2 = effect.generate_frame(ctx2)

        assert colors1 != colors2

    def test_pixels_vary_across_strip(self) -> None:
        """Test that not all pixels are identical on a multizone strip."""
        effect = EffectSpin(bulb_offset=5.0)
        ctx = FrameContext(
            elapsed_s=0.5,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)

        unique_hues = {c.hue for c in colors}
        assert len(unique_hues) > 1

    def test_elapsed_zero(self) -> None:
        """Test edge case with elapsed_s=0.0."""
        effect = EffectSpin()
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        assert len(colors) == 16
        for color in colors:
            assert 0.0 <= color.brightness <= 1.0

    def test_zones_per_bulb_groups_zones(self) -> None:
        """Test zones_per_bulb groups zones into logical bulbs."""
        effect = EffectSpin(zones_per_bulb=2, bulb_offset=0.0)
        ctx = FrameContext(
            elapsed_s=0.5,
            device_index=0,
            pixel_count=8,
            canvas_width=8,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        assert len(colors) == 8

        # Each pair of adjacent zones should have the same color
        for i in range(0, 8, 2):
            assert colors[i] == colors[i + 1]

    def test_single_pixel(self) -> None:
        """Test single-pixel device returns one color."""
        effect = EffectSpin()
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=1,
            canvas_width=1,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        assert len(colors) == 1


# ---------------------------------------------------------------------------
# Inheritance
# ---------------------------------------------------------------------------


class TestSpinInheritance:
    """Tests for EffectSpin class hierarchy."""

    def test_is_frame_effect(self) -> None:
        """Test EffectSpin extends FrameEffect."""
        effect = EffectSpin()
        assert isinstance(effect, FrameEffect)

    def test_is_lifx_effect(self) -> None:
        """Test EffectSpin extends LIFXEffect."""
        effect = EffectSpin()
        assert isinstance(effect, LIFXEffect)


# ---------------------------------------------------------------------------
# from_poweroff_hsbk
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_spin_from_poweroff_hsbk() -> None:
    """Test from_poweroff_hsbk returns first theme color at zero brightness."""
    custom_theme = Theme(
        [
            HSBK(hue=120, saturation=0.9, brightness=1.0, kelvin=3500),
            HSBK(hue=240, saturation=0.8, brightness=1.0, kelvin=3500),
        ]
    )
    effect = EffectSpin(theme=custom_theme, kelvin=5000)
    light = MagicMock()
    result = await effect.from_poweroff_hsbk(light)

    assert result.hue == 120
    assert result.saturation == 0.9
    assert result.brightness == 0.0
    assert result.kelvin == 5000


# ---------------------------------------------------------------------------
# is_light_compatible
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_spin_is_light_compatible_with_color() -> None:
    """Test is_light_compatible returns True for color lights."""
    effect = EffectSpin()
    light = MagicMock()
    capabilities = MagicMock()
    capabilities.has_color = True
    light.capabilities = capabilities

    assert await effect.is_light_compatible(light) is True


@pytest.mark.asyncio
async def test_spin_is_light_compatible_without_color() -> None:
    """Test is_light_compatible returns False for non-color lights."""
    effect = EffectSpin()
    light = MagicMock()
    capabilities = MagicMock()
    capabilities.has_color = False
    light.capabilities = capabilities

    assert await effect.is_light_compatible(light) is False


@pytest.mark.asyncio
async def test_spin_is_light_compatible_none_capabilities() -> None:
    """Test is_light_compatible loads capabilities when None."""
    effect = EffectSpin()
    light = MagicMock()
    light.capabilities = None

    async def ensure_caps() -> None:
        caps = MagicMock()
        caps.has_color = True
        light.capabilities = caps

    light._ensure_capabilities = AsyncMock(side_effect=ensure_caps)

    assert await effect.is_light_compatible(light) is True
    light._ensure_capabilities.assert_called_once()


# ---------------------------------------------------------------------------
# inherit_prestate
# ---------------------------------------------------------------------------


def test_spin_inherit_prestate() -> None:
    """Test inherit_prestate returns True for EffectSpin only."""
    effect = EffectSpin()
    assert effect.inherit_prestate(EffectSpin()) is True
    assert effect.inherit_prestate(MagicMock()) is False


# ---------------------------------------------------------------------------
# repr
# ---------------------------------------------------------------------------


def test_spin_repr() -> None:
    """Test EffectSpin string representation."""
    effect = EffectSpin(speed=5.0, brightness=0.6, kelvin=5000)
    repr_str = repr(effect)

    assert "EffectSpin" in repr_str
    assert "speed=5.0" in repr_str
    assert "brightness=0.6" in repr_str
    assert "kelvin=5000" in repr_str
