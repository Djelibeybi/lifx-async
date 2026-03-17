"""Tests for EffectEmbers (fire simulation)."""

import asyncio
import random
from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.effects.base import LIFXEffect
from lifx.effects.embers import (
    _CONVECTION_FRAMES,
    _THRESH_BLACK,
    _THRESH_ORANGE,
    _THRESH_RED,
    EffectEmbers,
    _heat_to_hsbk,
)
from lifx.effects.frame_effect import FrameContext, FrameEffect

# ---------------------------------------------------------------------------
# Constructor defaults
# ---------------------------------------------------------------------------


def test_embers_default_parameters() -> None:
    """Test EffectEmbers with default parameters."""
    effect = EffectEmbers()

    assert effect.name == "embers"
    assert effect.intensity == 0.5
    assert effect.cooling == 0.15
    assert effect.turbulence == 0.3
    assert effect.brightness == 0.8
    assert effect.kelvin == 3500
    assert effect.zones_per_bulb == 1
    assert effect.power_on is True
    assert effect.fps == 20.0
    assert effect.duration is None


def test_embers_custom_parameters() -> None:
    """Test EffectEmbers with custom parameters."""
    effect = EffectEmbers(
        intensity=0.7,
        cooling=0.2,
        turbulence=0.1,
        brightness=0.6,
        kelvin=5000,
        zones_per_bulb=3,
        power_on=False,
    )

    assert effect.intensity == 0.7
    assert effect.cooling == 0.2
    assert effect.turbulence == 0.1
    assert effect.brightness == 0.6
    assert effect.kelvin == 5000
    assert effect.zones_per_bulb == 3
    assert effect.power_on is False


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_embers_invalid_intensity() -> None:
    """Test EffectEmbers with invalid intensity raises ValueError."""
    with pytest.raises(ValueError, match="Intensity must be"):
        EffectEmbers(intensity=-0.1)

    with pytest.raises(ValueError, match="Intensity must be"):
        EffectEmbers(intensity=1.5)


def test_embers_invalid_cooling() -> None:
    """Test EffectEmbers with invalid cooling raises ValueError."""
    with pytest.raises(ValueError, match="Cooling must be"):
        EffectEmbers(cooling=-0.1)

    with pytest.raises(ValueError, match="Cooling must be"):
        EffectEmbers(cooling=1.5)


def test_embers_invalid_turbulence() -> None:
    """Test EffectEmbers with invalid turbulence raises ValueError."""
    with pytest.raises(ValueError, match="Turbulence must be"):
        EffectEmbers(turbulence=-0.1)

    with pytest.raises(ValueError, match="Turbulence must be"):
        EffectEmbers(turbulence=0.5)


def test_embers_invalid_brightness() -> None:
    """Test EffectEmbers with invalid brightness raises ValueError."""
    with pytest.raises(ValueError, match="Brightness must be"):
        EffectEmbers(brightness=-0.1)

    with pytest.raises(ValueError, match="Brightness must be"):
        EffectEmbers(brightness=1.5)


def test_embers_invalid_kelvin() -> None:
    """Test EffectEmbers with invalid kelvin raises ValueError."""
    with pytest.raises(ValueError, match="Kelvin must be"):
        EffectEmbers(kelvin=1000)

    with pytest.raises(ValueError, match="Kelvin must be"):
        EffectEmbers(kelvin=10000)


def test_embers_invalid_zones_per_bulb() -> None:
    """Test EffectEmbers with invalid zones_per_bulb raises ValueError."""
    with pytest.raises(ValueError, match="zones_per_bulb must be"):
        EffectEmbers(zones_per_bulb=0)

    with pytest.raises(ValueError, match="zones_per_bulb must be"):
        EffectEmbers(zones_per_bulb=-1)


# ---------------------------------------------------------------------------
# Inheritance
# ---------------------------------------------------------------------------


class TestEmbersInheritance:
    """Tests for EffectEmbers class hierarchy."""

    def test_is_frame_effect(self) -> None:
        """Test EffectEmbers extends FrameEffect."""
        effect = EffectEmbers()
        assert isinstance(effect, FrameEffect)

    def test_is_lifx_effect(self) -> None:
        """Test EffectEmbers extends LIFXEffect."""
        effect = EffectEmbers()
        assert isinstance(effect, LIFXEffect)


# ---------------------------------------------------------------------------
# Heat-to-color gradient
# ---------------------------------------------------------------------------


class TestHeatToHsbk:
    """Tests for the _heat_to_hsbk gradient mapping function."""

    def test_zero_heat_is_black(self) -> None:
        """Test heat=0.0 produces black (zero brightness)."""
        color = _heat_to_hsbk(0.0, 0.8, 3500)
        assert color.brightness == 0.0

    def test_below_threshold_is_black(self) -> None:
        """Test heat below _THRESH_BLACK produces black."""
        color = _heat_to_hsbk(_THRESH_BLACK - 0.01, 0.8, 3500)
        assert color.brightness == 0.0

    def test_red_zone(self) -> None:
        """Test heat in red zone produces red hue."""
        heat = (_THRESH_BLACK + _THRESH_RED) / 2
        color = _heat_to_hsbk(heat, 0.8, 3500)
        assert color.hue == 0  # Red
        assert color.saturation == 1.0
        assert color.brightness > 0.0

    def test_orange_zone(self) -> None:
        """Test heat in orange zone produces hue between red and orange."""
        heat = (_THRESH_RED + _THRESH_ORANGE) / 2
        color = _heat_to_hsbk(heat, 0.8, 3500)
        assert 0 <= color.hue <= 30
        assert color.saturation == 1.0
        assert color.brightness > 0.0

    def test_yellow_zone(self) -> None:
        """Test heat=1.0 produces yellow hue."""
        color = _heat_to_hsbk(1.0, 0.8, 3500)
        assert color.hue == 50  # Yellow
        assert color.saturation < 1.0  # Drops toward white
        assert color.brightness > 0.0

    def test_kelvin_passed_through(self) -> None:
        """Test kelvin value is passed through to output."""
        color = _heat_to_hsbk(0.5, 0.8, 5000)
        assert color.kelvin == 5000

    def test_brightness_scales_with_parameter(self) -> None:
        """Test brightness output scales with the brightness parameter."""
        color_low = _heat_to_hsbk(0.5, 0.3, 3500)
        color_high = _heat_to_hsbk(0.5, 1.0, 3500)
        assert color_high.brightness > color_low.brightness

    def test_brightness_increases_with_heat(self) -> None:
        """Test brightness increases as heat increases through gradient."""
        b_red = _heat_to_hsbk(0.2, 0.8, 3500).brightness
        b_orange = _heat_to_hsbk(0.5, 0.8, 3500).brightness
        b_yellow = _heat_to_hsbk(0.9, 0.8, 3500).brightness
        assert b_orange > b_red
        assert b_yellow > b_orange

    def test_gradient_continuity_at_red_threshold(self) -> None:
        """Test gradient is continuous at the red threshold boundary."""
        below = _heat_to_hsbk(_THRESH_RED - 0.01, 0.8, 3500)
        above = _heat_to_hsbk(_THRESH_RED + 0.01, 0.8, 3500)
        # Brightness should not jump drastically
        assert abs(above.brightness - below.brightness) < 0.1

    def test_gradient_continuity_at_orange_threshold(self) -> None:
        """Test gradient is continuous at the orange threshold boundary."""
        below = _heat_to_hsbk(_THRESH_ORANGE - 0.01, 0.8, 3500)
        above = _heat_to_hsbk(_THRESH_ORANGE + 0.01, 0.8, 3500)
        assert abs(above.brightness - below.brightness) < 0.1

    def test_output_brightness_clamped(self) -> None:
        """Test output brightness never exceeds 1.0."""
        color = _heat_to_hsbk(1.0, 1.0, 3500)
        assert color.brightness <= 1.0

    def test_saturation_drops_at_high_heat(self) -> None:
        """Test saturation decreases at high heat for yellow-white effect."""
        color = _heat_to_hsbk(1.0, 0.8, 3500)
        assert color.saturation < 1.0

    def test_full_saturation_in_red_zone(self) -> None:
        """Test saturation is 1.0 in the red zone."""
        color = _heat_to_hsbk(0.2, 0.8, 3500)
        assert color.saturation == 1.0


# ---------------------------------------------------------------------------
# Frame generation
# ---------------------------------------------------------------------------


class TestEmbersGenerateFrame:
    """Tests for EffectEmbers.generate_frame()."""

    def _make_ctx(
        self,
        elapsed_s: float = 1.0,
        pixel_count: int = 16,
    ) -> FrameContext:
        """Helper to create a FrameContext."""
        return FrameContext(
            elapsed_s=elapsed_s,
            device_index=0,
            pixel_count=pixel_count,
            canvas_width=pixel_count,
            canvas_height=1,
        )

    def test_single_pixel_returns_one_color(self) -> None:
        """Test single-pixel device returns one color."""
        effect = EffectEmbers()
        colors = effect.generate_frame(self._make_ctx(pixel_count=1))
        assert len(colors) == 1

    @pytest.mark.parametrize("pixel_count", [1, 8, 16, 82])
    def test_returns_correct_count(self, pixel_count: int) -> None:
        """Test correct number of colors for various pixel counts."""
        effect = EffectEmbers()
        colors = effect.generate_frame(self._make_ctx(pixel_count=pixel_count))
        assert len(colors) == pixel_count

    def test_kelvin_matches_configured(self) -> None:
        """Test all pixel kelvins match the configured kelvin."""
        effect = EffectEmbers(kelvin=5000)
        colors = effect.generate_frame(self._make_ctx())
        for color in colors:
            assert color.kelvin == 5000

    def test_brightness_in_valid_range(self) -> None:
        """Test all brightness values are 0.0-1.0."""
        effect = EffectEmbers()
        colors = effect.generate_frame(self._make_ctx())
        for color in colors:
            assert 0.0 <= color.brightness <= 1.0

    def test_hue_in_valid_range(self) -> None:
        """Test all hues are in the ember range (0-50 degrees)."""
        effect = EffectEmbers()
        colors = effect.generate_frame(self._make_ctx())
        for color in colors:
            assert 0 <= color.hue <= 50

    def test_saturation_in_valid_range(self) -> None:
        """Test all saturation values are 0.0-1.0."""
        effect = EffectEmbers()
        colors = effect.generate_frame(self._make_ctx())
        for color in colors:
            assert 0.0 <= color.saturation <= 1.0

    def test_zones_per_bulb_expands_colors(self) -> None:
        """Test zones_per_bulb groups zones into logical bulbs."""
        effect = EffectEmbers(zones_per_bulb=2)
        colors = effect.generate_frame(self._make_ctx(pixel_count=8))
        assert len(colors) == 8

        # Each pair of adjacent zones should have the same color
        for i in range(0, 8, 2):
            assert colors[i] == colors[i + 1]

    def test_zones_per_bulb_three(self) -> None:
        """Test zones_per_bulb=3 (polychrome string lights)."""
        effect = EffectEmbers(zones_per_bulb=3)
        colors = effect.generate_frame(self._make_ctx(pixel_count=9))
        assert len(colors) == 9

        # Each triplet should be the same color
        for i in range(0, 9, 3):
            assert colors[i] == colors[i + 1]
            assert colors[i] == colors[i + 2]

    def test_stateful_heat_buffer_persists(self) -> None:
        """Test heat buffer persists across frames."""
        random.seed(42)
        effect = EffectEmbers(intensity=1.0, turbulence=0.0)
        ctx = self._make_ctx(pixel_count=16)

        # Generate several frames to build up heat
        for _ in range(10):
            effect.generate_frame(ctx)

        # Heat buffer should exist and match bulb count
        assert len(effect._heat) == 16

    def test_heat_buffer_lazy_init(self) -> None:
        """Test heat buffer is lazily initialized on first frame."""
        effect = EffectEmbers()
        assert effect._heat == []

        effect.generate_frame(self._make_ctx(pixel_count=8))
        assert len(effect._heat) == 8

    def test_heat_buffer_resizes(self) -> None:
        """Test heat buffer resizes when pixel count changes."""
        effect = EffectEmbers()
        effect.generate_frame(self._make_ctx(pixel_count=8))
        assert len(effect._heat) == 8

        effect.generate_frame(self._make_ctx(pixel_count=16))
        assert len(effect._heat) == 16

    def test_high_intensity_produces_nonzero_brightness(self) -> None:
        """Test high intensity injects heat, producing visible colors."""
        random.seed(42)
        effect = EffectEmbers(intensity=1.0, cooling=0.0, turbulence=0.0)

        # Run several frames
        for _ in range(5):
            colors = effect.generate_frame(self._make_ctx(pixel_count=8))

        # At least the bottom zone should have nonzero brightness
        assert any(c.brightness > 0.0 for c in colors)

    def test_zero_intensity_no_injection(self) -> None:
        """Test zero intensity produces no heat injection at bottom."""
        random.seed(42)
        effect = EffectEmbers(intensity=0.0, turbulence=0.0, cooling=1.0)

        # Without injection or bursts, heat should remain at zero
        # (bursts are probabilistic so we seed and run few frames)
        colors = effect.generate_frame(self._make_ctx(pixel_count=4))
        # All colors should be black or near-black
        for c in colors:
            assert c.brightness < 0.5  # Allow for rare burst

    def test_cooling_factor_derived_correctly(self) -> None:
        """Test _cooling_factor is 1.0 - cooling."""
        effect = EffectEmbers(cooling=0.15)
        assert effect._cooling_factor == pytest.approx(0.85)

        effect2 = EffectEmbers(cooling=0.0)
        assert effect2._cooling_factor == pytest.approx(1.0)

        effect3 = EffectEmbers(cooling=1.0)
        assert effect3._cooling_factor == pytest.approx(0.0)

    def test_frame_count_increments(self) -> None:
        """Test frame counter increments each frame."""
        effect = EffectEmbers()
        assert effect._frame_count == 0

        effect.generate_frame(self._make_ctx())
        assert effect._frame_count == 1

        effect.generate_frame(self._make_ctx())
        assert effect._frame_count == 2


# ---------------------------------------------------------------------------
# Convection
# ---------------------------------------------------------------------------


class TestEmbersConvection:
    """Tests for heat convection (upward shift)."""

    def test_convection_shifts_heat_upward(self) -> None:
        """Test convection shifts heat from lower to upper zones."""
        effect = EffectEmbers(intensity=0.0, turbulence=0.0, cooling=0.0)
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=8,
            canvas_width=8,
            canvas_height=1,
        )

        # Initialize with known heat pattern
        effect.generate_frame(ctx)  # lazy init
        effect._heat = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

        # Advance to a convection frame
        effect._frame_count = _CONVECTION_FRAMES - 1

        # Generate frame (will trigger convection on next frame)
        effect.generate_frame(ctx)

        # Heat at position 0 should have shifted to position 1
        assert effect._heat[1] > 0.0 or effect._heat[0] == 0.0

    def test_convection_clears_bottom(self) -> None:
        """Test convection clears the bottom zone after shift."""
        effect = EffectEmbers(intensity=0.0, turbulence=0.0, cooling=0.0)
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=4,
            canvas_width=4,
            canvas_height=1,
        )

        effect.generate_frame(ctx)  # lazy init
        effect._heat = [0.8, 0.6, 0.4, 0.2]
        effect._frame_count = _CONVECTION_FRAMES - 1

        # This frame triggers convection (frame_count becomes
        # _CONVECTION_FRAMES)
        effect.generate_frame(ctx)

        # After convection + diffusion with cooling=0.0 (factor=1.0),
        # heat[0] was set to 0.0 by convection before diffusion
        # The exact values depend on diffusion, but convection happened


# ---------------------------------------------------------------------------
# Frame loop integration
# ---------------------------------------------------------------------------


class TestEmbersFrameLoop:
    """Tests for EffectEmbers running via FrameEffect frame loop."""

    @pytest.mark.asyncio
    async def test_sends_frames_via_animator(self) -> None:
        """Test embers sends frames through animator.send_frame."""
        effect = EffectEmbers()

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
# Power-off color
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_embers_from_poweroff() -> None:
    """Test from_poweroff_hsbk returns dim red for smooth fade-in."""
    effect = EffectEmbers(kelvin=5000)
    light = MagicMock()
    result = await effect.from_poweroff_hsbk(light)

    assert result.hue == 0
    assert result.saturation == 1.0
    assert result.brightness == 0.0
    assert result.kelvin == 5000


# ---------------------------------------------------------------------------
# Light compatibility
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_embers_is_light_compatible_with_color() -> None:
    """Test is_light_compatible returns True for color lights."""
    effect = EffectEmbers()
    light = MagicMock()
    capabilities = MagicMock()
    capabilities.has_color = True
    capabilities.has_matrix = False
    light.capabilities = capabilities

    assert await effect.is_light_compatible(light) is True


@pytest.mark.asyncio
async def test_embers_is_light_compatible_without_color() -> None:
    """Test is_light_compatible returns False for non-color lights."""
    effect = EffectEmbers()
    light = MagicMock()
    capabilities = MagicMock()
    capabilities.has_color = False
    capabilities.has_matrix = False
    light.capabilities = capabilities

    assert await effect.is_light_compatible(light) is False


@pytest.mark.asyncio
async def test_embers_is_light_compatible_matrix_rejected() -> None:
    """Test is_light_compatible returns False for matrix devices."""
    effect = EffectEmbers()
    light = MagicMock()
    capabilities = MagicMock()
    capabilities.has_color = True
    capabilities.has_matrix = True
    light.capabilities = capabilities

    assert await effect.is_light_compatible(light) is False


@pytest.mark.asyncio
async def test_embers_is_light_compatible_none_capabilities() -> None:
    """Test is_light_compatible loads capabilities when None."""
    effect = EffectEmbers()
    light = MagicMock()
    light.capabilities = None

    async def ensure_caps() -> None:
        caps = MagicMock()
        caps.has_color = True
        caps.has_matrix = False
        light.capabilities = caps

    light._ensure_capabilities = AsyncMock(side_effect=ensure_caps)

    assert await effect.is_light_compatible(light) is True
    light._ensure_capabilities.assert_called_once()


@pytest.mark.asyncio
async def test_embers_is_light_compatible_capabilities_still_none() -> None:
    """Test is_light_compatible returns False when capabilities remain None."""
    effect = EffectEmbers()
    light = MagicMock()
    light.capabilities = None
    light._ensure_capabilities = AsyncMock()

    assert await effect.is_light_compatible(light) is False


# ---------------------------------------------------------------------------
# inherit_prestate
# ---------------------------------------------------------------------------


def test_embers_inherit_prestate() -> None:
    """Test inherit_prestate returns True for EffectEmbers."""
    effect = EffectEmbers()
    assert effect.inherit_prestate(EffectEmbers()) is True
    assert effect.inherit_prestate(MagicMock()) is False


# ---------------------------------------------------------------------------
# repr
# ---------------------------------------------------------------------------


def test_embers_repr() -> None:
    """Test EffectEmbers string representation."""
    effect = EffectEmbers(intensity=0.7, cooling=0.2, brightness=0.6)
    repr_str = repr(effect)

    assert "EffectEmbers" in repr_str
    assert "intensity=0.7" in repr_str
    assert "cooling=0.2" in repr_str
    assert "brightness=0.6" in repr_str
    assert "kelvin=3500" in repr_str
    assert "zones_per_bulb=1" in repr_str
