"""Tests for EffectCylon (Larson scanner)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.effects.base import LIFXEffect
from lifx.effects.cylon import EffectCylon
from lifx.effects.frame_effect import FrameContext, FrameEffect


def test_cylon_default_parameters() -> None:
    """Test EffectCylon with default parameters."""
    effect = EffectCylon()

    assert effect.name == "cylon"
    assert effect.speed == 2.0
    assert effect.width == 3
    assert effect.hue == 0
    assert effect.brightness == 0.8
    assert effect.background_brightness == 0.0
    assert effect.trail == 0.5
    assert effect.kelvin == 3500
    assert effect.zones_per_bulb == 1
    assert effect.power_on is True
    assert effect.fps == 20.0
    assert effect.duration is None


def test_cylon_custom_parameters() -> None:
    """Test EffectCylon with custom parameters."""
    effect = EffectCylon(
        speed=4.0,
        width=5,
        hue=120,
        brightness=0.6,
        background_brightness=0.1,
        trail=0.8,
        kelvin=5000,
        zones_per_bulb=2,
        power_on=False,
    )

    assert effect.speed == 4.0
    assert effect.width == 5
    assert effect.hue == 120
    assert effect.brightness == 0.6
    assert effect.background_brightness == 0.1
    assert effect.trail == 0.8
    assert effect.kelvin == 5000
    assert effect.zones_per_bulb == 2
    assert effect.power_on is False


def test_cylon_invalid_speed() -> None:
    """Test EffectCylon with invalid speed raises ValueError."""
    with pytest.raises(ValueError, match="Speed must be"):
        EffectCylon(speed=0)

    with pytest.raises(ValueError, match="Speed must be"):
        EffectCylon(speed=-1.0)


def test_cylon_invalid_width() -> None:
    """Test EffectCylon with invalid width raises ValueError."""
    with pytest.raises(ValueError, match="Width must be"):
        EffectCylon(width=0)

    with pytest.raises(ValueError, match="Width must be"):
        EffectCylon(width=-1)


def test_cylon_invalid_hue() -> None:
    """Test EffectCylon with invalid hue raises ValueError."""
    with pytest.raises(ValueError, match="Hue must be"):
        EffectCylon(hue=-1)

    with pytest.raises(ValueError, match="Hue must be"):
        EffectCylon(hue=361)


def test_cylon_invalid_brightness() -> None:
    """Test EffectCylon with invalid brightness raises ValueError."""
    with pytest.raises(ValueError, match="Brightness must be"):
        EffectCylon(brightness=1.5)

    with pytest.raises(ValueError, match="Brightness must be"):
        EffectCylon(brightness=-0.1)


def test_cylon_invalid_background_brightness() -> None:
    """Test EffectCylon with invalid background_brightness raises ValueError."""
    with pytest.raises(ValueError, match="Background brightness must be"):
        EffectCylon(background_brightness=1.5)

    with pytest.raises(ValueError, match="Background brightness must be"):
        EffectCylon(background_brightness=-0.1)


def test_cylon_invalid_trail() -> None:
    """Test EffectCylon with invalid trail raises ValueError."""
    with pytest.raises(ValueError, match="Trail must be"):
        EffectCylon(trail=1.5)

    with pytest.raises(ValueError, match="Trail must be"):
        EffectCylon(trail=-0.1)


def test_cylon_invalid_kelvin() -> None:
    """Test EffectCylon with invalid kelvin raises ValueError."""
    with pytest.raises(ValueError, match="Kelvin must be"):
        EffectCylon(kelvin=1000)

    with pytest.raises(ValueError, match="Kelvin must be"):
        EffectCylon(kelvin=10000)


def test_cylon_invalid_zones_per_bulb() -> None:
    """Test EffectCylon with invalid zones_per_bulb raises ValueError."""
    with pytest.raises(ValueError, match="zones_per_bulb must be"):
        EffectCylon(zones_per_bulb=0)

    with pytest.raises(ValueError, match="zones_per_bulb must be"):
        EffectCylon(zones_per_bulb=-1)


class TestCylonInheritance:
    """Tests for EffectCylon class hierarchy."""

    def test_is_frame_effect(self) -> None:
        """Test EffectCylon extends FrameEffect."""
        effect = EffectCylon()
        assert isinstance(effect, FrameEffect)

    def test_is_lifx_effect(self) -> None:
        """Test EffectCylon extends LIFXEffect."""
        effect = EffectCylon()
        assert isinstance(effect, LIFXEffect)


class TestCylonGenerateFrame:
    """Tests for EffectCylon.generate_frame()."""

    def test_single_pixel_returns_one_color(self) -> None:
        """Test single-pixel device returns one color."""
        effect = EffectCylon()
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=1,
            canvas_width=1,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        assert len(colors) == 1

    @pytest.mark.parametrize("pixel_count", [1, 8, 16, 82])
    def test_multi_pixel_returns_correct_count(self, pixel_count: int) -> None:
        """Test correct number of colors for various pixel counts."""
        effect = EffectCylon()
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=pixel_count,
            canvas_width=pixel_count,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        assert len(colors) == pixel_count

    def test_hue_matches_configured(self) -> None:
        """Test all pixel hues match the configured hue."""
        effect = EffectCylon(hue=120)
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        for color in colors:
            assert color.hue == 120

    def test_saturation_is_full(self) -> None:
        """Test all pixels have full saturation."""
        effect = EffectCylon()
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        for color in colors:
            assert color.saturation == 1.0

    def test_kelvin_matches_configured(self) -> None:
        """Test kelvin values match configured kelvin."""
        effect = EffectCylon(kelvin=5000)
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        for color in colors:
            assert color.kelvin == 5000

    def test_brightness_in_valid_range(self) -> None:
        """Test all brightness values are 0.0-1.0."""
        effect = EffectCylon()
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        for color in colors:
            assert 0.0 <= color.brightness <= 1.0

    def test_frame_changes_over_time(self) -> None:
        """Test different elapsed_s produce different frames."""
        effect = EffectCylon()
        ctx1 = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=8,
            canvas_width=8,
            canvas_height=1,
        )
        ctx2 = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=8,
            canvas_width=8,
            canvas_height=1,
        )
        colors1 = effect.generate_frame(ctx1)
        colors2 = effect.generate_frame(ctx2)

        # At least some pixels should differ
        assert colors1 != colors2

    def test_pixels_vary_across_strip(self) -> None:
        """Test pixels are not all identical on a multizone strip."""
        effect = EffectCylon(brightness=0.8, background_brightness=0.0)
        ctx = FrameContext(
            elapsed_s=0.5,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)

        # Not all pixels should be the same brightness
        unique_brightnesses = {c.brightness for c in colors}
        assert len(unique_brightnesses) > 1

    def test_elapsed_zero(self) -> None:
        """Test edge case with elapsed_s=0.0."""
        effect = EffectCylon()
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

    def test_zones_per_bulb_expands_colors(self) -> None:
        """Test zones_per_bulb groups zones into logical bulbs."""
        effect = EffectCylon(zones_per_bulb=2)
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


class TestCylonFrameLoop:
    """Tests for EffectCylon running via FrameEffect frame loop."""

    @pytest.mark.asyncio
    async def test_sends_frames_via_animator(self) -> None:
        """Test cylon sends frames through animator.send_frame."""
        effect = EffectCylon()

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


@pytest.mark.asyncio
async def test_cylon_from_poweroff() -> None:
    """Test from_poweroff_hsbk returns dim version of eye color."""
    effect = EffectCylon(hue=120, kelvin=5000)
    light = MagicMock()
    result = await effect.from_poweroff_hsbk(light)

    assert result.hue == 120
    assert result.saturation == 1.0
    assert result.brightness == 0.0
    assert result.kelvin == 5000


@pytest.mark.asyncio
async def test_cylon_is_light_compatible_with_color() -> None:
    """Test is_light_compatible returns True for color lights."""
    effect = EffectCylon()
    light = MagicMock()
    capabilities = MagicMock()
    capabilities.has_color = True
    light.capabilities = capabilities

    assert await effect.is_light_compatible(light) is True


@pytest.mark.asyncio
async def test_cylon_is_light_compatible_without_color() -> None:
    """Test is_light_compatible returns False for non-color lights."""
    effect = EffectCylon()
    light = MagicMock()
    capabilities = MagicMock()
    capabilities.has_color = False
    light.capabilities = capabilities

    assert await effect.is_light_compatible(light) is False


@pytest.mark.asyncio
async def test_cylon_is_light_compatible_none_capabilities() -> None:
    """Test is_light_compatible loads capabilities when None."""
    effect = EffectCylon()
    light = MagicMock()
    light.capabilities = None

    async def ensure_caps() -> None:
        caps = MagicMock()
        caps.has_color = True
        light.capabilities = caps

    light.ensure_capabilities = AsyncMock(side_effect=ensure_caps)

    assert await effect.is_light_compatible(light) is True
    light.ensure_capabilities.assert_called_once()


def test_cylon_inherit_prestate() -> None:
    """Test inherit_prestate returns True for EffectCylon."""
    effect = EffectCylon()
    assert effect.inherit_prestate(EffectCylon()) is True
    assert effect.inherit_prestate(MagicMock()) is False


def test_cylon_repr() -> None:
    """Test EffectCylon string representation."""
    effect = EffectCylon(speed=4.0, width=5, hue=120, brightness=0.6)
    repr_str = repr(effect)

    assert "EffectCylon" in repr_str
    assert "speed=4.0" in repr_str
    assert "width=5" in repr_str
    assert "hue=120" in repr_str
    assert "brightness=0.6" in repr_str
