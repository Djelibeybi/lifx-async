"""Tests for EffectWave (standing wave)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.effects.base import LIFXEffect
from lifx.effects.frame_effect import FrameContext, FrameEffect
from lifx.effects.wave import EffectWave


def test_wave_default_parameters() -> None:
    """Test EffectWave with default parameters."""
    effect = EffectWave()

    assert effect.name == "wave"
    assert effect.speed == 4.0
    assert effect.nodes == 2
    assert effect.hue1 == 0
    assert effect.hue2 == 240
    assert effect.saturation1 == 1.0
    assert effect.saturation2 == 1.0
    assert effect.brightness == 0.8
    assert effect.drift == 0.0
    assert effect.kelvin == 3500
    assert effect.zones_per_bulb == 1
    assert effect.power_on is True
    assert effect.fps == 20.0
    assert effect.duration is None


def test_wave_custom_parameters() -> None:
    """Test EffectWave with custom parameters."""
    effect = EffectWave(
        speed=6.0,
        nodes=4,
        hue1=120,
        hue2=300,
        saturation1=0.5,
        saturation2=0.8,
        brightness=0.6,
        drift=45.0,
        kelvin=5000,
        zones_per_bulb=3,
        power_on=False,
    )

    assert effect.speed == 6.0
    assert effect.nodes == 4
    assert effect.hue1 == 120
    assert effect.hue2 == 300
    assert effect.saturation1 == 0.5
    assert effect.saturation2 == 0.8
    assert effect.brightness == 0.6
    assert effect.drift == 45.0
    assert effect.kelvin == 5000
    assert effect.zones_per_bulb == 3
    assert effect.power_on is False


def test_wave_invalid_speed() -> None:
    """Test EffectWave with invalid speed raises ValueError."""
    with pytest.raises(ValueError, match="Speed must be"):
        EffectWave(speed=0)

    with pytest.raises(ValueError, match="Speed must be"):
        EffectWave(speed=-1.0)


def test_wave_invalid_nodes() -> None:
    """Test EffectWave with invalid nodes raises ValueError."""
    with pytest.raises(ValueError, match="Nodes must be"):
        EffectWave(nodes=0)

    with pytest.raises(ValueError, match="Nodes must be"):
        EffectWave(nodes=-1)


def test_wave_invalid_hue1() -> None:
    """Test EffectWave with invalid hue1 raises ValueError."""
    with pytest.raises(ValueError, match="hue1 must be"):
        EffectWave(hue1=-1)

    with pytest.raises(ValueError, match="hue1 must be"):
        EffectWave(hue1=361)


def test_wave_invalid_hue2() -> None:
    """Test EffectWave with invalid hue2 raises ValueError."""
    with pytest.raises(ValueError, match="hue2 must be"):
        EffectWave(hue2=-1)

    with pytest.raises(ValueError, match="hue2 must be"):
        EffectWave(hue2=361)


def test_wave_invalid_saturation1() -> None:
    """Test EffectWave with invalid saturation1 raises ValueError."""
    with pytest.raises(ValueError, match="saturation1 must be"):
        EffectWave(saturation1=1.5)

    with pytest.raises(ValueError, match="saturation1 must be"):
        EffectWave(saturation1=-0.1)


def test_wave_invalid_saturation2() -> None:
    """Test EffectWave with invalid saturation2 raises ValueError."""
    with pytest.raises(ValueError, match="saturation2 must be"):
        EffectWave(saturation2=1.5)

    with pytest.raises(ValueError, match="saturation2 must be"):
        EffectWave(saturation2=-0.1)


def test_wave_invalid_brightness() -> None:
    """Test EffectWave with invalid brightness raises ValueError."""
    with pytest.raises(ValueError, match="Brightness must be"):
        EffectWave(brightness=1.5)

    with pytest.raises(ValueError, match="Brightness must be"):
        EffectWave(brightness=-0.1)


def test_wave_invalid_kelvin() -> None:
    """Test EffectWave with invalid kelvin raises ValueError."""
    with pytest.raises(ValueError, match="Kelvin must be"):
        EffectWave(kelvin=1000)

    with pytest.raises(ValueError, match="Kelvin must be"):
        EffectWave(kelvin=10000)


def test_wave_invalid_zones_per_bulb() -> None:
    """Test EffectWave with invalid zones_per_bulb raises ValueError."""
    with pytest.raises(ValueError, match="zones_per_bulb must be"):
        EffectWave(zones_per_bulb=0)

    with pytest.raises(ValueError, match="zones_per_bulb must be"):
        EffectWave(zones_per_bulb=-1)


class TestWaveInheritance:
    """Tests for EffectWave class hierarchy."""

    def test_is_frame_effect(self) -> None:
        """Test EffectWave extends FrameEffect."""
        effect = EffectWave()
        assert isinstance(effect, FrameEffect)

    def test_is_lifx_effect(self) -> None:
        """Test EffectWave extends LIFXEffect."""
        effect = EffectWave()
        assert isinstance(effect, LIFXEffect)


class TestWaveGenerateFrame:
    """Tests for EffectWave.generate_frame()."""

    def test_single_pixel_returns_one_color(self) -> None:
        """Test single-pixel device returns one color."""
        effect = EffectWave()
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
        effect = EffectWave()
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=pixel_count,
            canvas_width=pixel_count,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        assert len(colors) == pixel_count

    def test_valid_hsbk_output(self) -> None:
        """Test all output HSBK values are within valid ranges."""
        effect = EffectWave()
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        for color in colors:
            assert 0 <= color.hue <= 360
            assert 0.0 <= color.saturation <= 1.0
            assert 0.0 <= color.brightness <= 1.0
            assert 1500 <= color.kelvin <= 9000

    def test_kelvin_matches_configured(self) -> None:
        """Test kelvin values match configured kelvin."""
        effect = EffectWave(kelvin=5000)
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
        effect = EffectWave()
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
        effect = EffectWave()
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
        effect = EffectWave(nodes=3)
        ctx = FrameContext(
            elapsed_s=0.5,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)

        # Not all pixels should be the same hue with multiple nodes
        unique_hues = {c.hue for c in colors}
        assert len(unique_hues) > 1

    def test_elapsed_zero(self) -> None:
        """Test edge case with elapsed_s=0.0."""
        effect = EffectWave()
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
        effect = EffectWave(zones_per_bulb=2)
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

    def test_single_bulb_produces_temporal_oscillation(self) -> None:
        """Test single-pixel device uses full antinode amplitude."""
        effect = EffectWave(speed=4.0)
        # At t=0 temporal=sin(0)=0, at t=1 temporal=sin(pi/2)=1
        ctx_t0 = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=1,
            canvas_width=1,
            canvas_height=1,
        )
        ctx_t1 = FrameContext(
            elapsed_s=1.0,  # speed=4 -> phase=0.25 -> sin(pi/2)=1
            device_index=0,
            pixel_count=1,
            canvas_width=1,
            canvas_height=1,
        )
        colors_t0 = effect.generate_frame(ctx_t0)
        colors_t1 = effect.generate_frame(ctx_t1)

        # At t=0, temporal=0 so blend=0.5 (midpoint between colors)
        # At t=1, temporal=1 so blend=1.0 (color2)
        # These should differ
        assert colors_t0[0] != colors_t1[0]

    def test_drift_creates_traveling_wave(self) -> None:
        """Test nonzero drift causes spatial pattern to shift over time."""
        effect_static = EffectWave(drift=0.0, nodes=3)
        effect_drift = EffectWave(drift=90.0, nodes=3)

        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )

        colors_static = effect_static.generate_frame(ctx)
        colors_drift = effect_drift.generate_frame(ctx)

        # With drift, the pattern should be spatially shifted
        assert colors_static != colors_drift


class TestWaveFrameLoop:
    """Tests for EffectWave running via FrameEffect frame loop."""

    @pytest.mark.asyncio
    async def test_sends_frames_via_animator(self) -> None:
        """Test wave sends frames through animator.send_frame."""
        effect = EffectWave()

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
async def test_wave_from_poweroff() -> None:
    """Test from_poweroff_hsbk returns dim midpoint color."""
    effect = EffectWave(hue1=0, hue2=240, kelvin=5000)
    light = MagicMock()
    result = await effect.from_poweroff_hsbk(light)

    assert result.brightness == 0.0
    assert result.kelvin == 5000


@pytest.mark.asyncio
async def test_wave_is_light_compatible_with_color() -> None:
    """Test is_light_compatible returns True for color lights."""
    effect = EffectWave()
    light = MagicMock()
    capabilities = MagicMock()
    capabilities.has_color = True
    light.capabilities = capabilities

    assert await effect.is_light_compatible(light) is True


@pytest.mark.asyncio
async def test_wave_is_light_compatible_without_color() -> None:
    """Test is_light_compatible returns False for non-color lights."""
    effect = EffectWave()
    light = MagicMock()
    capabilities = MagicMock()
    capabilities.has_color = False
    light.capabilities = capabilities

    assert await effect.is_light_compatible(light) is False


@pytest.mark.asyncio
async def test_wave_is_light_compatible_none_capabilities() -> None:
    """Test is_light_compatible loads capabilities when None."""
    effect = EffectWave()
    light = MagicMock()
    light.capabilities = None

    async def ensure_caps() -> None:
        caps = MagicMock()
        caps.has_color = True
        light.capabilities = caps

    light.ensure_capabilities = AsyncMock(side_effect=ensure_caps)

    assert await effect.is_light_compatible(light) is True
    light.ensure_capabilities.assert_called_once()


def test_wave_inherit_prestate() -> None:
    """Test inherit_prestate returns True for EffectWave."""
    effect = EffectWave()
    assert effect.inherit_prestate(EffectWave()) is True
    assert effect.inherit_prestate(MagicMock()) is False


def test_wave_zones_per_bulb_padding() -> None:
    """Test output is padded when zones don't fill pixel_count."""
    effect = EffectWave(zones_per_bulb=3)
    ctx = FrameContext(
        elapsed_s=0.5, device_index=0, pixel_count=17, canvas_width=17, canvas_height=1
    )
    colors = effect.generate_frame(ctx)
    assert len(colors) == 17


def test_wave_zones_per_bulb_trimming() -> None:
    """Test output is trimmed when zones exceed pixel_count."""
    effect = EffectWave(zones_per_bulb=3)
    ctx = FrameContext(
        elapsed_s=0.5, device_index=0, pixel_count=1, canvas_width=1, canvas_height=1
    )
    colors = effect.generate_frame(ctx)
    assert len(colors) == 1


def test_wave_repr() -> None:
    """Test EffectWave string representation."""
    effect = EffectWave(speed=6.0, nodes=4, hue1=120, hue2=300)
    repr_str = repr(effect)

    assert "EffectWave" in repr_str
    assert "speed=6.0" in repr_str
    assert "nodes=4" in repr_str
    assert "hue1=120" in repr_str
    assert "hue2=300" in repr_str
