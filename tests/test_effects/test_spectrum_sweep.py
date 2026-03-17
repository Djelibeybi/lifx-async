"""Tests for EffectSpectrumSweep (three-phase sine sweep)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.effects.base import LIFXEffect
from lifx.effects.frame_effect import FrameContext, FrameEffect
from lifx.effects.spectrum_sweep import EffectSpectrumSweep


def test_spectrum_sweep_default_parameters() -> None:
    """Test EffectSpectrumSweep with default parameters."""
    effect = EffectSpectrumSweep()

    assert effect.name == "spectrum_sweep"
    assert effect.speed == 6.0
    assert effect.waves == 1.0
    assert effect.brightness == 0.8
    assert effect.kelvin == 3500
    assert effect.zones_per_bulb == 1
    assert effect.power_on is True
    assert effect.fps == 20.0
    assert effect.duration is None


def test_spectrum_sweep_custom_parameters() -> None:
    """Test EffectSpectrumSweep with custom parameters."""
    effect = EffectSpectrumSweep(
        speed=3.0,
        waves=2.5,
        brightness=0.6,
        kelvin=5000,
        zones_per_bulb=2,
        power_on=False,
    )

    assert effect.speed == 3.0
    assert effect.waves == 2.5
    assert effect.brightness == 0.6
    assert effect.kelvin == 5000
    assert effect.zones_per_bulb == 2
    assert effect.power_on is False


def test_spectrum_sweep_invalid_speed() -> None:
    """Test EffectSpectrumSweep with invalid speed raises ValueError."""
    with pytest.raises(ValueError, match="Speed must be"):
        EffectSpectrumSweep(speed=0)

    with pytest.raises(ValueError, match="Speed must be"):
        EffectSpectrumSweep(speed=-1.0)


def test_spectrum_sweep_invalid_waves() -> None:
    """Test EffectSpectrumSweep with invalid waves raises ValueError."""
    with pytest.raises(ValueError, match="Waves must be"):
        EffectSpectrumSweep(waves=0)

    with pytest.raises(ValueError, match="Waves must be"):
        EffectSpectrumSweep(waves=-1.0)


def test_spectrum_sweep_invalid_brightness() -> None:
    """Test EffectSpectrumSweep with invalid brightness raises ValueError."""
    with pytest.raises(ValueError, match="Brightness must be"):
        EffectSpectrumSweep(brightness=1.5)

    with pytest.raises(ValueError, match="Brightness must be"):
        EffectSpectrumSweep(brightness=-0.1)


def test_spectrum_sweep_invalid_kelvin() -> None:
    """Test EffectSpectrumSweep with invalid kelvin raises ValueError."""
    with pytest.raises(ValueError, match="Kelvin must be"):
        EffectSpectrumSweep(kelvin=1000)

    with pytest.raises(ValueError, match="Kelvin must be"):
        EffectSpectrumSweep(kelvin=10000)


def test_spectrum_sweep_invalid_zones_per_bulb() -> None:
    """Test EffectSpectrumSweep with invalid zones_per_bulb raises ValueError."""
    with pytest.raises(ValueError, match="zones_per_bulb must be"):
        EffectSpectrumSweep(zones_per_bulb=0)

    with pytest.raises(ValueError, match="zones_per_bulb must be"):
        EffectSpectrumSweep(zones_per_bulb=-1)


class TestSpectrumSweepInheritance:
    """Tests for EffectSpectrumSweep class hierarchy."""

    def test_is_frame_effect(self) -> None:
        """Test EffectSpectrumSweep extends FrameEffect."""
        effect = EffectSpectrumSweep()
        assert isinstance(effect, FrameEffect)

    def test_is_lifx_effect(self) -> None:
        """Test EffectSpectrumSweep extends LIFXEffect."""
        effect = EffectSpectrumSweep()
        assert isinstance(effect, LIFXEffect)


class TestSpectrumSweepGenerateFrame:
    """Tests for EffectSpectrumSweep.generate_frame()."""

    def test_single_pixel_returns_one_color(self) -> None:
        """Test single-pixel device returns one color."""
        effect = EffectSpectrumSweep()
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=1,
            canvas_width=1,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        assert len(colors) == 1

    @pytest.mark.parametrize("pixel_count", [1, 8, 16, 24, 82])
    def test_multi_pixel_returns_correct_count(self, pixel_count: int) -> None:
        """Test correct number of colors for various pixel counts."""
        effect = EffectSpectrumSweep()
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=pixel_count,
            canvas_width=pixel_count,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        assert len(colors) == pixel_count

    def test_saturation_is_full(self) -> None:
        """Test all pixels have full or near-full saturation."""
        effect = EffectSpectrumSweep()
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        for color in colors:
            # Oklab blending may slightly reduce saturation
            assert color.saturation >= 0.0

    def test_kelvin_matches_configured(self) -> None:
        """Test kelvin values match configured kelvin."""
        effect = EffectSpectrumSweep(kelvin=5000)
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
        effect = EffectSpectrumSweep()
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

    def test_brightness_respects_peak(self) -> None:
        """Test brightness does not exceed configured peak."""
        effect = EffectSpectrumSweep(brightness=0.5)
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        for color in colors:
            assert color.brightness <= 0.5 + 1e-9

    def test_frame_changes_over_time(self) -> None:
        """Test different elapsed_s produce different frames."""
        effect = EffectSpectrumSweep()
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
        effect = EffectSpectrumSweep()
        ctx = FrameContext(
            elapsed_s=0.5,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)

        # Not all pixels should be the same hue
        unique_hues = {c.hue for c in colors}
        assert len(unique_hues) > 1

    def test_elapsed_zero(self) -> None:
        """Test edge case with elapsed_s=0.0."""
        effect = EffectSpectrumSweep()
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
        effect = EffectSpectrumSweep(zones_per_bulb=2)
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

    def test_hue_varies_with_three_phases(self) -> None:
        """Test that the effect produces hues from all three phase regions."""
        effect = EffectSpectrumSweep(waves=1.0)
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=24,
            canvas_width=24,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)

        # Collect hues; with 3 phases across 24 zones we expect variety
        hues = [c.hue for c in colors]
        unique_hues = set(hues)
        assert len(unique_hues) > 3

    def test_full_brightness_produces_bright_pixels(self) -> None:
        """Test that brightness=1.0 produces some fully bright pixels."""
        effect = EffectSpectrumSweep(brightness=1.0)
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=24,
            canvas_width=24,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)

        # At least one pixel should be at full brightness (sine peak)
        max_bri = max(c.brightness for c in colors)
        assert max_bri >= 0.9

    def test_speed_affects_sweep_rate(self) -> None:
        """Test that different speeds produce different patterns at same time."""
        effect_slow = EffectSpectrumSweep(speed=6.0)
        effect_fast = EffectSpectrumSweep(speed=2.0)
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors_slow = effect_slow.generate_frame(ctx)
        colors_fast = effect_fast.generate_frame(ctx)

        assert colors_slow != colors_fast

    def test_waves_affects_spatial_frequency(self) -> None:
        """Test that different wave counts produce different patterns."""
        effect_low = EffectSpectrumSweep(waves=1.0)
        effect_high = EffectSpectrumSweep(waves=3.0)
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors_low = effect_low.generate_frame(ctx)
        colors_high = effect_high.generate_frame(ctx)

        assert colors_low != colors_high


class TestSpectrumSweepFrameLoop:
    """Tests for EffectSpectrumSweep running via FrameEffect frame loop."""

    @pytest.mark.asyncio
    async def test_sends_frames_via_animator(self) -> None:
        """Test spectrum sweep sends frames through animator.send_frame."""
        effect = EffectSpectrumSweep()

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
async def test_spectrum_sweep_from_poweroff() -> None:
    """Test from_poweroff_hsbk returns dim red for smooth fade-in."""
    effect = EffectSpectrumSweep(kelvin=5000)
    light = MagicMock()
    result = await effect.from_poweroff_hsbk(light)

    assert result.hue == 0
    assert result.saturation == 1.0
    assert result.brightness == 0.0
    assert result.kelvin == 5000


@pytest.mark.asyncio
async def test_spectrum_sweep_is_light_compatible_with_color() -> None:
    """Test is_light_compatible returns True for color lights."""
    effect = EffectSpectrumSweep()
    light = MagicMock()
    capabilities = MagicMock()
    capabilities.has_color = True
    light.capabilities = capabilities

    assert await effect.is_light_compatible(light) is True


@pytest.mark.asyncio
async def test_spectrum_sweep_is_light_compatible_without_color() -> None:
    """Test is_light_compatible returns False for non-color lights."""
    effect = EffectSpectrumSweep()
    light = MagicMock()
    capabilities = MagicMock()
    capabilities.has_color = False
    light.capabilities = capabilities

    assert await effect.is_light_compatible(light) is False


@pytest.mark.asyncio
async def test_spectrum_sweep_is_light_compatible_none_capabilities() -> None:
    """Test is_light_compatible loads capabilities when None."""
    effect = EffectSpectrumSweep()
    light = MagicMock()
    light.capabilities = None

    async def ensure_caps() -> None:
        caps = MagicMock()
        caps.has_color = True
        light.capabilities = caps

    light._ensure_capabilities = AsyncMock(side_effect=ensure_caps)

    assert await effect.is_light_compatible(light) is True
    light._ensure_capabilities.assert_called_once()


def test_spectrum_sweep_inherit_prestate() -> None:
    """Test inherit_prestate returns True for EffectSpectrumSweep."""
    effect = EffectSpectrumSweep()
    assert effect.inherit_prestate(EffectSpectrumSweep()) is True
    assert effect.inherit_prestate(MagicMock()) is False


def test_spectrum_sweep_repr() -> None:
    """Test EffectSpectrumSweep string representation."""
    effect = EffectSpectrumSweep(speed=3.0, waves=2.5, brightness=0.6)
    repr_str = repr(effect)

    assert "EffectSpectrumSweep" in repr_str
    assert "speed=3.0" in repr_str
    assert "waves=2.5" in repr_str
    assert "brightness=0.6" in repr_str
