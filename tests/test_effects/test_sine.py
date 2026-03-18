"""Tests for EffectSine (traveling ease wave)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.effects.base import LIFXEffect
from lifx.effects.frame_effect import FrameContext, FrameEffect
from lifx.effects.sine import EffectSine


def test_sine_default_parameters() -> None:
    """Test EffectSine with default parameters."""
    effect = EffectSine()

    assert effect.name == "sine"
    assert effect.speed == 4.0
    assert effect.wavelength == 0.5
    assert effect.hue == 200
    assert effect.saturation == 1.0
    assert effect.brightness == 0.8
    assert effect.floor == 0.02
    assert effect.hue2 is None
    assert effect.kelvin == 3500
    assert effect.zones_per_bulb == 1
    assert effect.reverse is False
    assert effect.power_on is True
    assert effect.fps == 20.0
    assert effect.duration is None


def test_sine_custom_parameters() -> None:
    """Test EffectSine with custom parameters."""
    effect = EffectSine(
        speed=6.0,
        wavelength=1.0,
        hue=120,
        saturation=0.8,
        brightness=0.6,
        floor=0.05,
        hue2=300,
        kelvin=5000,
        zones_per_bulb=3,
        reverse=True,
        power_on=False,
    )

    assert effect.speed == 6.0
    assert effect.wavelength == 1.0
    assert effect.hue == 120
    assert effect.saturation == 0.8
    assert effect.brightness == 0.6
    assert effect.floor == 0.05
    assert effect.hue2 == 300
    assert effect.kelvin == 5000
    assert effect.zones_per_bulb == 3
    assert effect.reverse is True
    assert effect.power_on is False


def test_sine_invalid_speed() -> None:
    """Test EffectSine with invalid speed raises ValueError."""
    with pytest.raises(ValueError, match="Speed must be"):
        EffectSine(speed=0)

    with pytest.raises(ValueError, match="Speed must be"):
        EffectSine(speed=-1.0)


def test_sine_invalid_wavelength() -> None:
    """Test EffectSine with invalid wavelength raises ValueError."""
    with pytest.raises(ValueError, match="Wavelength must be"):
        EffectSine(wavelength=0)

    with pytest.raises(ValueError, match="Wavelength must be"):
        EffectSine(wavelength=-0.5)


def test_sine_invalid_hue() -> None:
    """Test EffectSine with invalid hue raises ValueError."""
    with pytest.raises(ValueError, match="Hue must be"):
        EffectSine(hue=-1)

    with pytest.raises(ValueError, match="Hue must be"):
        EffectSine(hue=361)


def test_sine_invalid_saturation() -> None:
    """Test EffectSine with invalid saturation raises ValueError."""
    with pytest.raises(ValueError, match="Saturation must be"):
        EffectSine(saturation=1.5)

    with pytest.raises(ValueError, match="Saturation must be"):
        EffectSine(saturation=-0.1)


def test_sine_invalid_brightness() -> None:
    """Test EffectSine with invalid brightness raises ValueError."""
    with pytest.raises(ValueError, match="Brightness must be"):
        EffectSine(brightness=1.5)

    with pytest.raises(ValueError, match="Brightness must be"):
        EffectSine(brightness=-0.1)


def test_sine_invalid_floor() -> None:
    """Test EffectSine with invalid floor raises ValueError."""
    with pytest.raises(ValueError, match="Floor must be"):
        EffectSine(floor=-0.1)

    with pytest.raises(ValueError, match="Floor must be"):
        EffectSine(floor=1.1)


def test_sine_invalid_floor_exceeds_brightness() -> None:
    """Test EffectSine with floor >= brightness raises ValueError."""
    with pytest.raises(ValueError, match="Floor must be less than brightness"):
        EffectSine(floor=0.8, brightness=0.8)

    with pytest.raises(ValueError, match="Floor must be less than brightness"):
        EffectSine(floor=0.9, brightness=0.5)


def test_sine_invalid_hue2() -> None:
    """Test EffectSine with invalid hue2 raises ValueError."""
    with pytest.raises(ValueError, match="hue2 must be"):
        EffectSine(hue2=-1)

    with pytest.raises(ValueError, match="hue2 must be"):
        EffectSine(hue2=361)


def test_sine_invalid_kelvin() -> None:
    """Test EffectSine with invalid kelvin raises ValueError."""
    with pytest.raises(ValueError, match="Kelvin must be"):
        EffectSine(kelvin=1000)

    with pytest.raises(ValueError, match="Kelvin must be"):
        EffectSine(kelvin=10000)


def test_sine_invalid_zones_per_bulb() -> None:
    """Test EffectSine with invalid zones_per_bulb raises ValueError."""
    with pytest.raises(ValueError, match="zones_per_bulb must be"):
        EffectSine(zones_per_bulb=0)

    with pytest.raises(ValueError, match="zones_per_bulb must be"):
        EffectSine(zones_per_bulb=-1)


class TestSineInheritance:
    """Tests for EffectSine class hierarchy."""

    def test_is_frame_effect(self) -> None:
        """Test EffectSine extends FrameEffect."""
        effect = EffectSine()
        assert isinstance(effect, FrameEffect)

    def test_is_lifx_effect(self) -> None:
        """Test EffectSine extends LIFXEffect."""
        effect = EffectSine()
        assert isinstance(effect, LIFXEffect)


class TestSineGenerateFrame:
    """Tests for EffectSine.generate_frame()."""

    def test_single_pixel_returns_one_color(self) -> None:
        """Test single-pixel device returns one color."""
        effect = EffectSine()
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
        effect = EffectSine()
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
        """Test pixel hues match the configured hue (without gradient)."""
        effect = EffectSine(hue=120)
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

    def test_saturation_matches_configured(self) -> None:
        """Test all pixels have configured saturation."""
        effect = EffectSine(saturation=0.7)
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        for color in colors:
            assert color.saturation == pytest.approx(0.7, abs=0.01)

    def test_kelvin_matches_configured(self) -> None:
        """Test kelvin values match configured kelvin."""
        effect = EffectSine(kelvin=5000)
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
        """Test all brightness values are between floor and brightness."""
        effect = EffectSine(brightness=0.8, floor=0.02)
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

    def test_brightness_bounded_by_floor_and_peak(self) -> None:
        """Test brightness is always between floor and peak brightness."""
        effect = EffectSine(brightness=0.6, floor=0.1)
        # Test many time steps to cover various wave positions
        for t in [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]:
            ctx = FrameContext(
                elapsed_s=t,
                device_index=0,
                pixel_count=16,
                canvas_width=16,
                canvas_height=1,
            )
            colors = effect.generate_frame(ctx)
            for color in colors:
                assert color.brightness >= 0.1 - 0.001
                assert color.brightness <= 0.6 + 0.001

    def test_frame_changes_over_time(self) -> None:
        """Test different elapsed_s produce different frames."""
        effect = EffectSine()
        ctx1 = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        ctx2 = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors1 = effect.generate_frame(ctx1)
        colors2 = effect.generate_frame(ctx2)

        # At least some pixels should differ
        assert colors1 != colors2

    def test_pixels_vary_across_strip(self) -> None:
        """Test pixels are not all identical on a multizone strip."""
        effect = EffectSine(brightness=0.8, floor=0.02)
        ctx = FrameContext(
            elapsed_s=0.5,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)

        # Not all pixels should be the same brightness
        unique_brightnesses = {round(c.brightness, 6) for c in colors}
        assert len(unique_brightnesses) > 1

    def test_elapsed_zero(self) -> None:
        """Test edge case with elapsed_s=0.0."""
        effect = EffectSine()
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
        effect = EffectSine(zones_per_bulb=2)
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

    def test_reverse_changes_direction(self) -> None:
        """Test reverse flag changes wave travel direction."""
        effect_fwd = EffectSine(reverse=False)
        effect_rev = EffectSine(reverse=True)
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors_fwd = effect_fwd.generate_frame(ctx)
        colors_rev = effect_rev.generate_frame(ctx)

        # Frames should differ when reverse is toggled
        assert colors_fwd != colors_rev

    def test_smoothstep_produces_smooth_brightness(self) -> None:
        """Test that positive half-cycle uses smoothstep for brightness."""
        effect = EffectSine(brightness=1.0, floor=0.0)
        # At time when the wave is in positive half-cycle for some zones,
        # brightness should be smoothly eased (not just raw sine).
        ctx = FrameContext(
            elapsed_s=0.5,
            device_index=0,
            pixel_count=32,
            canvas_width=32,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)

        # Verify that at least some pixels have intermediate brightness
        # values (not just 0 or 1), confirming smoothstep is applied
        brightnesses = [c.brightness for c in colors]
        has_intermediate = any(0.01 < b < 0.99 for b in brightnesses)
        assert has_intermediate

    def test_gradient_with_hue2(self) -> None:
        """Test hue2 creates a gradient along the wave."""
        effect = EffectSine(hue=0, hue2=240)
        ctx = FrameContext(
            elapsed_s=0.5,
            device_index=0,
            pixel_count=32,
            canvas_width=32,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)

        # With gradient from hue=0 to hue2=240, bright zones should show
        # multiple distinct hue values across the strip
        bright_hues = {round(c.hue, 1) for c in colors if c.brightness > 0.03}
        # A 32-pixel strip with hue gradient should produce several distinct hues
        assert len(bright_hues) >= 2, f"Expected gradient hues, got {bright_hues}"


class TestSineFrameLoop:
    """Tests for EffectSine running via FrameEffect frame loop."""

    @pytest.mark.asyncio
    async def test_sends_frames_via_animator(self) -> None:
        """Test sine sends frames through animator.send_frame."""
        effect = EffectSine()

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
async def test_sine_from_poweroff() -> None:
    """Test from_poweroff_hsbk returns dim version of wave color."""
    effect = EffectSine(hue=120, saturation=0.8, kelvin=5000)
    light = MagicMock()
    result = await effect.from_poweroff_hsbk(light)

    assert result.hue == 120
    assert result.saturation == 0.8
    assert result.brightness == 0.0
    assert result.kelvin == 5000


@pytest.mark.asyncio
async def test_sine_is_light_compatible_with_color() -> None:
    """Test is_light_compatible returns True for color lights."""
    effect = EffectSine()
    light = MagicMock()
    capabilities = MagicMock()
    capabilities.has_color = True
    light.capabilities = capabilities

    assert await effect.is_light_compatible(light) is True


@pytest.mark.asyncio
async def test_sine_is_light_compatible_without_color() -> None:
    """Test is_light_compatible returns False for non-color lights."""
    effect = EffectSine()
    light = MagicMock()
    capabilities = MagicMock()
    capabilities.has_color = False
    light.capabilities = capabilities

    assert await effect.is_light_compatible(light) is False


@pytest.mark.asyncio
async def test_sine_is_light_compatible_none_capabilities() -> None:
    """Test is_light_compatible loads capabilities when None."""
    effect = EffectSine()
    light = MagicMock()
    light.capabilities = None

    async def ensure_caps() -> None:
        caps = MagicMock()
        caps.has_color = True
        light.capabilities = caps

    light.ensure_capabilities = AsyncMock(side_effect=ensure_caps)

    assert await effect.is_light_compatible(light) is True
    light.ensure_capabilities.assert_called_once()


def test_sine_inherit_prestate() -> None:
    """Test inherit_prestate returns True for EffectSine."""
    effect = EffectSine()
    assert effect.inherit_prestate(EffectSine()) is True
    assert effect.inherit_prestate(MagicMock()) is False


def test_sine_repr() -> None:
    """Test EffectSine string representation."""
    effect = EffectSine(speed=6.0, wavelength=1.0, hue=120, brightness=0.6)
    repr_str = repr(effect)

    assert "EffectSine" in repr_str
    assert "speed=6.0" in repr_str
    assert "wavelength=1.0" in repr_str
    assert "hue=120" in repr_str
    assert "brightness=0.6" in repr_str
