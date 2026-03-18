"""Tests for EffectDoubleSlit (double slit wave interference)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.effects.base import LIFXEffect
from lifx.effects.double_slit import EffectDoubleSlit
from lifx.effects.frame_effect import FrameContext, FrameEffect

# ---------------------------------------------------------------------------
# Construction / defaults
# ---------------------------------------------------------------------------


def test_double_slit_default_parameters() -> None:
    """Test EffectDoubleSlit with default parameters."""
    effect = EffectDoubleSlit()

    assert effect.name == "double_slit"
    assert effect.speed == 4.0
    assert effect.wavelength == 0.3
    assert effect.separation == 0.2
    assert effect.breathe == 0.0
    assert effect.hue1 == 0
    assert effect.hue2 == 240
    assert effect.saturation == 1.0
    assert effect.brightness == 0.8
    assert effect.kelvin == 3500
    assert effect.zones_per_bulb == 1
    assert effect.power_on is True
    assert effect.fps == 20.0
    assert effect.duration is None


def test_double_slit_custom_parameters() -> None:
    """Test EffectDoubleSlit with custom parameters."""
    effect = EffectDoubleSlit(
        speed=6.0,
        wavelength=0.5,
        separation=0.4,
        breathe=20.0,
        hue1=120,
        hue2=300,
        saturation=0.7,
        brightness=0.6,
        kelvin=5000,
        zones_per_bulb=3,
        power_on=False,
    )

    assert effect.speed == 6.0
    assert effect.wavelength == 0.5
    assert effect.separation == 0.4
    assert effect.breathe == 20.0
    assert effect.hue1 == 120
    assert effect.hue2 == 300
    assert effect.saturation == 0.7
    assert effect.brightness == 0.6
    assert effect.kelvin == 5000
    assert effect.zones_per_bulb == 3
    assert effect.power_on is False


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_invalid_speed() -> None:
    """Test EffectDoubleSlit with invalid speed raises ValueError."""
    with pytest.raises(ValueError, match="Speed must be"):
        EffectDoubleSlit(speed=0)

    with pytest.raises(ValueError, match="Speed must be"):
        EffectDoubleSlit(speed=-1.0)


def test_invalid_wavelength() -> None:
    """Test EffectDoubleSlit with invalid wavelength raises ValueError."""
    with pytest.raises(ValueError, match="Wavelength must be"):
        EffectDoubleSlit(wavelength=0.01)

    with pytest.raises(ValueError, match="Wavelength must be"):
        EffectDoubleSlit(wavelength=3.0)


def test_invalid_separation() -> None:
    """Test EffectDoubleSlit with invalid separation raises ValueError."""
    with pytest.raises(ValueError, match="Separation must be"):
        EffectDoubleSlit(separation=0.01)

    with pytest.raises(ValueError, match="Separation must be"):
        EffectDoubleSlit(separation=1.0)


def test_invalid_breathe() -> None:
    """Test EffectDoubleSlit with negative breathe raises ValueError."""
    with pytest.raises(ValueError, match="Breathe must be"):
        EffectDoubleSlit(breathe=-1.0)


def test_invalid_hue1() -> None:
    """Test EffectDoubleSlit with invalid hue1 raises ValueError."""
    with pytest.raises(ValueError, match="hue1 must be"):
        EffectDoubleSlit(hue1=-1)

    with pytest.raises(ValueError, match="hue1 must be"):
        EffectDoubleSlit(hue1=361)


def test_invalid_hue2() -> None:
    """Test EffectDoubleSlit with invalid hue2 raises ValueError."""
    with pytest.raises(ValueError, match="hue2 must be"):
        EffectDoubleSlit(hue2=-1)

    with pytest.raises(ValueError, match="hue2 must be"):
        EffectDoubleSlit(hue2=361)


def test_invalid_saturation() -> None:
    """Test EffectDoubleSlit with invalid saturation raises ValueError."""
    with pytest.raises(ValueError, match="Saturation must be"):
        EffectDoubleSlit(saturation=1.5)

    with pytest.raises(ValueError, match="Saturation must be"):
        EffectDoubleSlit(saturation=-0.1)


def test_invalid_brightness() -> None:
    """Test EffectDoubleSlit with invalid brightness raises ValueError."""
    with pytest.raises(ValueError, match="Brightness must be"):
        EffectDoubleSlit(brightness=1.5)

    with pytest.raises(ValueError, match="Brightness must be"):
        EffectDoubleSlit(brightness=-0.1)


def test_invalid_kelvin() -> None:
    """Test EffectDoubleSlit with invalid kelvin raises ValueError."""
    with pytest.raises(ValueError, match="Kelvin must be"):
        EffectDoubleSlit(kelvin=1000)

    with pytest.raises(ValueError, match="Kelvin must be"):
        EffectDoubleSlit(kelvin=10000)


def test_invalid_zones_per_bulb() -> None:
    """Test EffectDoubleSlit with invalid zones_per_bulb raises ValueError."""
    with pytest.raises(ValueError, match="zones_per_bulb must be"):
        EffectDoubleSlit(zones_per_bulb=0)

    with pytest.raises(ValueError, match="zones_per_bulb must be"):
        EffectDoubleSlit(zones_per_bulb=-1)


# ---------------------------------------------------------------------------
# Inheritance
# ---------------------------------------------------------------------------


class TestDoubleSlitInheritance:
    """Tests for EffectDoubleSlit class hierarchy."""

    def test_is_frame_effect(self) -> None:
        """Test EffectDoubleSlit extends FrameEffect."""
        effect = EffectDoubleSlit()
        assert isinstance(effect, FrameEffect)

    def test_is_lifx_effect(self) -> None:
        """Test EffectDoubleSlit extends LIFXEffect."""
        effect = EffectDoubleSlit()
        assert isinstance(effect, LIFXEffect)


# ---------------------------------------------------------------------------
# generate_frame()
# ---------------------------------------------------------------------------


class TestDoubleSlitGenerateFrame:
    """Tests for EffectDoubleSlit.generate_frame()."""

    def _ctx(
        self,
        elapsed_s: float = 1.0,
        pixel_count: int = 16,
    ) -> FrameContext:
        return FrameContext(
            elapsed_s=elapsed_s,
            device_index=0,
            pixel_count=pixel_count,
            canvas_width=pixel_count,
            canvas_height=1,
        )

    def test_single_pixel_returns_one_color(self) -> None:
        """Test single-pixel device returns one color."""
        effect = EffectDoubleSlit()
        colors = effect.generate_frame(self._ctx(pixel_count=1))
        assert len(colors) == 1

    @pytest.mark.parametrize("pixel_count", [1, 8, 16, 82])
    def test_multi_pixel_returns_correct_count(self, pixel_count: int) -> None:
        """Test correct number of colors for various pixel counts."""
        effect = EffectDoubleSlit()
        colors = effect.generate_frame(self._ctx(pixel_count=pixel_count))
        assert len(colors) == pixel_count

    def test_valid_hsbk_output(self) -> None:
        """Test all output HSBK values are within valid ranges."""
        effect = EffectDoubleSlit()
        colors = effect.generate_frame(self._ctx())
        for color in colors:
            assert 0 <= color.hue <= 360
            assert 0.0 <= color.saturation <= 1.0
            assert 0.0 <= color.brightness <= 1.0
            assert 1500 <= color.kelvin <= 9000

    def test_kelvin_matches_configured(self) -> None:
        """Test kelvin values match configured kelvin."""
        effect = EffectDoubleSlit(kelvin=5000)
        colors = effect.generate_frame(self._ctx())
        for color in colors:
            assert color.kelvin == 5000

    def test_brightness_bounded_by_configured(self) -> None:
        """Test brightness does not exceed configured brightness."""
        effect = EffectDoubleSlit(brightness=0.6)
        colors = effect.generate_frame(self._ctx())
        for color in colors:
            assert color.brightness <= 0.6 + 1e-9

    def test_frame_changes_over_time(self) -> None:
        """Test different elapsed_s produce different frames."""
        effect = EffectDoubleSlit()
        colors1 = effect.generate_frame(self._ctx(elapsed_s=0.0))
        colors2 = effect.generate_frame(self._ctx(elapsed_s=1.0))

        # At least some pixels should differ
        assert colors1 != colors2

    def test_pixels_vary_across_strip(self) -> None:
        """Test pixels are not all identical on a multizone strip."""
        effect = EffectDoubleSlit()
        colors = effect.generate_frame(self._ctx(elapsed_s=0.5, pixel_count=16))

        # With interference, not all pixels should be the same
        unique_hues = {c.hue for c in colors}
        assert len(unique_hues) > 1

    def test_elapsed_zero(self) -> None:
        """Test edge case with elapsed_s=0.0."""
        effect = EffectDoubleSlit()
        colors = effect.generate_frame(self._ctx(elapsed_s=0.0))
        assert len(colors) == 16
        for color in colors:
            assert 0.0 <= color.brightness <= 1.0

    def test_zones_per_bulb_expands_colors(self) -> None:
        """Test zones_per_bulb groups zones into logical bulbs."""
        effect = EffectDoubleSlit(zones_per_bulb=2)
        colors = effect.generate_frame(self._ctx(pixel_count=8))
        assert len(colors) == 8

        # Each pair of adjacent zones should have the same color
        for i in range(0, 8, 2):
            assert colors[i] == colors[i + 1]

    def test_zones_per_bulb_trims_to_pixel_count(self) -> None:
        """Test zones_per_bulb with non-divisible pixel count trims correctly."""
        effect = EffectDoubleSlit(zones_per_bulb=3)
        colors = effect.generate_frame(self._ctx(pixel_count=10))
        assert len(colors) == 10

    def test_interference_pattern_symmetric(self) -> None:
        """Test that interference pattern is symmetric about center.

        With sources symmetric about center, the pattern should be
        approximately symmetric. We check the inner portion of the strip
        where edge effects are minimal.
        """
        effect = EffectDoubleSlit(separation=0.4)
        # Use a large pixel count for clear symmetry
        n = 40
        colors = effect.generate_frame(self._ctx(elapsed_s=0.0, pixel_count=n))

        # Check brightness symmetry for the inner 60% of the strip
        # (edges diverge due to discrete sampling and asymmetric source distances)
        start = n // 5
        end = n - start
        for i in range(start, end):
            j = n - 1 - i
            if j <= i:
                break
            assert abs(colors[i].brightness - colors[j].brightness) < 0.4

    def test_breathe_modulates_wavelength(self) -> None:
        """Test that breathe parameter modulates the pattern over time."""
        effect_static = EffectDoubleSlit(breathe=0.0)
        effect_breathe = EffectDoubleSlit(breathe=10.0)

        # At t=0, breathe has no effect (sin(0)=0)
        colors_static_0 = effect_static.generate_frame(self._ctx(elapsed_s=0.0))
        colors_breathe_0 = effect_breathe.generate_frame(self._ctx(elapsed_s=0.0))
        assert colors_static_0 == colors_breathe_0

        # At t=2.5 (quarter of breathe period), breathe changes the pattern
        colors_static_2 = effect_static.generate_frame(self._ctx(elapsed_s=2.5))
        colors_breathe_2 = effect_breathe.generate_frame(self._ctx(elapsed_s=2.5))
        assert colors_static_2 != colors_breathe_2

    def test_separation_affects_fringe_spacing(self) -> None:
        """Test wider separation changes the interference pattern."""
        narrow = EffectDoubleSlit(separation=0.1)
        wide = EffectDoubleSlit(separation=0.5)

        colors_narrow = narrow.generate_frame(self._ctx(elapsed_s=0.5))
        colors_wide = wide.generate_frame(self._ctx(elapsed_s=0.5))

        # Different separations should produce different patterns
        assert colors_narrow != colors_wide

    def test_constructive_interference_brighter(self) -> None:
        """Test that constructive interference zones are brighter.

        At a source position, d1=0 so wave1=sin(-omega*t). Both waves
        contribute, and where they align the amplitude should be larger
        than at destructive interference points.
        """
        effect = EffectDoubleSlit(brightness=1.0)
        colors = effect.generate_frame(self._ctx(elapsed_s=0.5, pixel_count=32))

        brightnesses = [c.brightness for c in colors]
        max_bri = max(brightnesses)
        min_bri = min(brightnesses)

        # There should be visible contrast in brightness
        assert max_bri > min_bri


# ---------------------------------------------------------------------------
# Frame loop
# ---------------------------------------------------------------------------


class TestDoubleSlitFrameLoop:
    """Tests for EffectDoubleSlit running via FrameEffect frame loop."""

    @pytest.mark.asyncio
    async def test_sends_frames_via_animator(self) -> None:
        """Test double slit sends frames through animator.send_frame."""
        effect = EffectDoubleSlit()

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


# ---------------------------------------------------------------------------
# Lifecycle hooks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_double_slit_from_poweroff() -> None:
    """Test from_poweroff_hsbk returns dim midpoint color."""
    effect = EffectDoubleSlit(hue1=0, hue2=240, kelvin=5000)
    light = MagicMock()
    result = await effect.from_poweroff_hsbk(light)

    assert result.brightness == 0.0
    assert result.kelvin == 5000


@pytest.mark.asyncio
async def test_double_slit_is_light_compatible_with_color() -> None:
    """Test is_light_compatible returns True for color lights."""
    effect = EffectDoubleSlit()
    light = MagicMock()
    capabilities = MagicMock()
    capabilities.has_color = True
    light.capabilities = capabilities

    assert await effect.is_light_compatible(light) is True


@pytest.mark.asyncio
async def test_double_slit_is_light_compatible_without_color() -> None:
    """Test is_light_compatible returns False for non-color lights."""
    effect = EffectDoubleSlit()
    light = MagicMock()
    capabilities = MagicMock()
    capabilities.has_color = False
    light.capabilities = capabilities

    assert await effect.is_light_compatible(light) is False


@pytest.mark.asyncio
async def test_double_slit_is_light_compatible_none_capabilities() -> None:
    """Test is_light_compatible loads capabilities when None."""
    effect = EffectDoubleSlit()
    light = MagicMock()
    light.capabilities = None

    async def ensure_caps() -> None:
        caps = MagicMock()
        caps.has_color = True
        light.capabilities = caps

    light.ensure_capabilities = AsyncMock(side_effect=ensure_caps)

    assert await effect.is_light_compatible(light) is True
    light.ensure_capabilities.assert_called_once()


# ---------------------------------------------------------------------------
# inherit_prestate / repr
# ---------------------------------------------------------------------------


def test_double_slit_inherit_prestate() -> None:
    """Test inherit_prestate returns True for EffectDoubleSlit."""
    effect = EffectDoubleSlit()
    assert effect.inherit_prestate(EffectDoubleSlit()) is True
    assert effect.inherit_prestate(MagicMock()) is False


def test_double_slit_repr() -> None:
    """Test EffectDoubleSlit string representation."""
    effect = EffectDoubleSlit(speed=6.0, wavelength=0.5, separation=0.4)
    repr_str = repr(effect)

    assert "EffectDoubleSlit" in repr_str
    assert "speed=6.0" in repr_str
    assert "wavelength=0.5" in repr_str
    assert "separation=0.4" in repr_str
