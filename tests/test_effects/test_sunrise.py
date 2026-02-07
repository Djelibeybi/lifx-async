"""Tests for EffectSunrise and EffectSunset."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.const import KELVIN_COOL
from lifx.effects.base import LIFXEffect
from lifx.effects.frame_effect import FrameContext, FrameEffect
from lifx.effects.sunrise import EffectSunrise, EffectSunset

# ============================================================================
# EffectSunrise Tests
# ============================================================================


def test_sunrise_default_parameters():
    """Test EffectSunrise with default parameters."""
    effect = EffectSunrise()

    assert effect.name == "sunrise"
    assert effect.duration == 60.0
    assert effect.brightness == 1.0
    assert effect.power_on is True
    assert effect.origin == "bottom"
    assert effect.fps == 20.0


def test_sunrise_custom_parameters():
    """Test EffectSunrise with custom parameters."""
    effect = EffectSunrise(
        duration=120, brightness=0.8, power_on=False, origin="center"
    )

    assert effect.duration == 120
    assert effect.brightness == 0.8
    assert effect.power_on is False
    assert effect.origin == "center"


def test_sunrise_invalid_duration():
    """Test EffectSunrise with invalid duration raises ValueError."""
    with pytest.raises(ValueError, match="Duration must be positive"):
        EffectSunrise(duration=0)

    with pytest.raises(ValueError, match="Duration must be positive"):
        EffectSunrise(duration=-1)


def test_sunrise_invalid_brightness():
    """Test EffectSunrise with invalid brightness raises ValueError."""
    with pytest.raises(ValueError, match="Brightness must be 0.0-1.0"):
        EffectSunrise(brightness=1.5)


def test_sunrise_invalid_origin():
    """Test EffectSunrise with invalid origin raises ValueError."""
    with pytest.raises(ValueError, match="Origin must be 'bottom' or 'center'"):
        EffectSunrise(origin="top")  # type: ignore[arg-type]


class TestSunriseInheritance:
    """Tests for EffectSunrise class hierarchy."""

    def test_is_frame_effect(self) -> None:
        """Test EffectSunrise extends FrameEffect."""
        effect = EffectSunrise()
        assert isinstance(effect, FrameEffect)

    def test_is_lifx_effect(self) -> None:
        """Test EffectSunrise extends LIFXEffect."""
        effect = EffectSunrise()
        assert isinstance(effect, LIFXEffect)


class TestSunriseGenerateFrame:
    """Tests for EffectSunrise.generate_frame()."""

    def test_start_is_dark(self) -> None:
        """Test that start of sunrise (elapsed=0) is dark (night)."""
        effect = EffectSunrise(duration=60)
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=64,
            canvas_width=8,
            canvas_height=8,
        )
        colors = effect.generate_frame(ctx)

        avg_brightness = sum(c.brightness for c in colors) / len(colors)
        assert avg_brightness < 0.2

    def test_end_is_bright(self) -> None:
        """Test that end of sunrise (elapsed=duration) is bright (day)."""
        effect = EffectSunrise(duration=60, brightness=1.0)
        ctx = FrameContext(
            elapsed_s=60.0,
            device_index=0,
            pixel_count=64,
            canvas_width=8,
            canvas_height=8,
        )
        colors = effect.generate_frame(ctx)

        avg_brightness = sum(c.brightness for c in colors) / len(colors)
        assert avg_brightness > 0.3

    def test_midpoint_golden_hour(self) -> None:
        """Test midpoint has warm hues (golden hour range)."""
        effect = EffectSunrise(duration=60)
        ctx = FrameContext(
            elapsed_s=30.0,
            device_index=0,
            pixel_count=64,
            canvas_width=8,
            canvas_height=8,
        )
        colors = effect.generate_frame(ctx)

        # At midpoint (~progress=0.5), should have warm hues
        hues = [c.hue for c in colors]
        # At least some pixels should be in warm range (0-60 or 300-360)
        warm_pixels = sum(1 for h in hues if h <= 60 or h >= 300)
        assert warm_pixels > 0

    def test_bottom_brighter_than_top_during_rise(self) -> None:
        """Test horizon effect — pixels near sun are brighter."""
        effect = EffectSunrise(duration=60)
        # At progress ~0.3, sun is somewhere in the middle area
        ctx = FrameContext(
            elapsed_s=18.0,  # 30% of 60s
            device_index=0,
            pixel_count=64,
            canvas_width=8,
            canvas_height=8,
        )
        colors = effect.generate_frame(ctx)

        # Check that brightness varies vertically
        row_brightness = []
        for row in range(8):
            start = row * 8
            avg = sum(colors[start + i].brightness for i in range(8)) / 8
            row_brightness.append(avg)

        # Not all rows should have identical brightness
        assert len(set(row_brightness)) > 1

    def test_radial_expansion_from_bottom_center(self) -> None:
        """Test sun expands radially from bottom-center of canvas."""
        effect = EffectSunrise(duration=60)
        # At ~40% progress, center should be well ahead of corners
        ctx = FrameContext(
            elapsed_s=24.0,  # 40% of 60s
            device_index=0,
            pixel_count=64,
            canvas_width=8,
            canvas_height=8,
        )
        colors = effect.generate_frame(ctx)

        # Bottom-center pixel (row 7, col 3) should be brightest
        bottom_center = colors[7 * 8 + 3]
        # Top-left corner (row 0, col 0) should be dimmest
        top_corner = colors[0]
        assert bottom_center.brightness > top_corner.brightness

        # Bottom-center should be in a warmer phase than top corner
        # (lower hue = warmer for golden/orange vs higher hue for blue/purple)
        # Top corner should still be in night (hue ~240) or dawn (hue ~280+)
        assert top_corner.hue > bottom_center.hue or top_corner.hue >= 200

    def test_radial_expansion_from_center(self) -> None:
        """Test sun expands radially from center of canvas (for Ceiling lights)."""
        effect = EffectSunrise(duration=60, origin="center")
        ctx = FrameContext(
            elapsed_s=24.0,  # 40% of 60s
            device_index=0,
            pixel_count=64,
            canvas_width=8,
            canvas_height=8,
        )
        colors = effect.generate_frame(ctx)

        # Center pixel (row 3, col 3) should be brightest
        center = colors[3 * 8 + 3]
        # Corner pixel (row 0, col 0) should be dimmest
        corner = colors[0]
        assert center.brightness > corner.brightness

        # All four corners should be roughly equal brightness (symmetric)
        top_left = colors[0]
        top_right = colors[7]
        bottom_left = colors[7 * 8]
        bottom_right = colors[7 * 8 + 7]
        corner_brightnesses = [
            top_left.brightness,
            top_right.brightness,
            bottom_left.brightness,
            bottom_right.brightness,
        ]
        assert max(corner_brightnesses) - min(corner_brightnesses) < 0.05

    def test_colors_progress_through_phases(self) -> None:
        """Test that hues transition from cool to warm over time."""
        effect = EffectSunrise(duration=100)

        # Night phase — expect blue-ish hues (around 240)
        ctx_night = FrameContext(
            elapsed_s=5.0,
            device_index=0,
            pixel_count=64,
            canvas_width=8,
            canvas_height=8,
        )
        colors_night = effect.generate_frame(ctx_night)

        # Day phase — expect low hue or low saturation
        ctx_day = FrameContext(
            elapsed_s=95.0,
            device_index=0,
            pixel_count=64,
            canvas_width=8,
            canvas_height=8,
        )
        colors_day = effect.generate_frame(ctx_day)

        # Night should be more saturated/blue, day should be less saturated
        avg_sat_night = sum(c.saturation for c in colors_night) / len(colors_night)
        avg_sat_day = sum(c.saturation for c in colors_day) / len(colors_day)
        assert avg_sat_night > avg_sat_day

    @pytest.mark.parametrize("canvas_size", [(8, 8), (16, 16), (40, 8)])
    def test_frame_at_various_canvas_sizes(self, canvas_size: tuple[int, int]) -> None:
        """Test frame generation for different canvas sizes."""
        w, h = canvas_size
        effect = EffectSunrise(duration=60)
        ctx = FrameContext(
            elapsed_s=30.0,
            device_index=0,
            pixel_count=w * h,
            canvas_width=w,
            canvas_height=h,
        )
        colors = effect.generate_frame(ctx)
        assert len(colors) == w * h


class TestSunriseCompatibility:
    """Tests for EffectSunrise device compatibility."""

    @pytest.mark.asyncio
    async def test_compatible_with_matrix(self) -> None:
        """Test is_light_compatible returns True for matrix lights."""
        effect = EffectSunrise()
        light = MagicMock()
        capabilities = MagicMock()
        capabilities.has_matrix = True
        light.capabilities = capabilities

        assert await effect.is_light_compatible(light) is True

    @pytest.mark.asyncio
    async def test_incompatible_with_non_matrix(self) -> None:
        """Test is_light_compatible returns False for non-matrix lights."""
        effect = EffectSunrise()
        light = MagicMock()
        capabilities = MagicMock()
        capabilities.has_matrix = False
        light.capabilities = capabilities

        assert await effect.is_light_compatible(light) is False

    @pytest.mark.asyncio
    async def test_loads_capabilities_when_none(self) -> None:
        """Test is_light_compatible loads capabilities when None."""
        effect = EffectSunrise()
        light = MagicMock()
        light.capabilities = None

        async def ensure_caps():
            caps = MagicMock()
            caps.has_matrix = True
            light.capabilities = caps

        light._ensure_capabilities = AsyncMock(side_effect=ensure_caps)

        assert await effect.is_light_compatible(light) is True
        light._ensure_capabilities.assert_called_once()


class TestSunriseFrameLoop:
    """Tests for EffectSunrise running via FrameEffect frame loop."""

    @pytest.mark.asyncio
    async def test_sends_frames_and_stops_at_duration(self) -> None:
        """Test sunrise sends frames and stops after duration."""
        effect = EffectSunrise(duration=0.2)

        animator = MagicMock()
        animator.pixel_count = 64
        animator.canvas_width = 8
        animator.canvas_height = 8
        animator.send_frame = MagicMock()
        effect._animators = [animator]

        # Should complete within duration + small buffer
        await asyncio.wait_for(effect.async_play(), timeout=2.0)
        assert animator.send_frame.call_count > 0


@pytest.mark.asyncio
async def test_sunrise_from_poweroff():
    """Test from_poweroff_hsbk returns deep navy."""
    effect = EffectSunrise()
    light = MagicMock()
    result = await effect.from_poweroff_hsbk(light)

    assert result.hue == 240
    assert result.saturation == 0.8
    assert result.brightness == 0.0


def test_sunrise_inherit_prestate():
    """Test inherit_prestate returns True for EffectSunrise."""
    effect = EffectSunrise()
    assert effect.inherit_prestate(EffectSunrise()) is True
    assert effect.inherit_prestate(MagicMock()) is False


def test_sunrise_restore_on_complete_is_false():
    """Test sunrise skips state restoration on completion."""
    effect = EffectSunrise()
    assert effect.restore_on_complete is False


def test_sunrise_repr():
    """Test EffectSunrise string representation."""
    effect = EffectSunrise(duration=120, brightness=0.8)
    repr_str = repr(effect)

    assert "EffectSunrise" in repr_str
    assert "duration=120" in repr_str
    assert "brightness=0.8" in repr_str
    assert "origin='bottom'" in repr_str


def test_sunrise_repr_center_origin():
    """Test EffectSunrise repr with center origin."""
    effect = EffectSunrise(duration=60, origin="center")
    repr_str = repr(effect)

    assert "origin='center'" in repr_str


# ============================================================================
# EffectSunset Tests
# ============================================================================


def test_sunset_default_parameters():
    """Test EffectSunset with default parameters."""
    effect = EffectSunset()

    assert effect.name == "sunset"
    assert effect.duration == 60.0
    assert effect.brightness == 1.0
    assert effect.power_on is False
    assert effect.power_off is True
    assert effect.origin == "bottom"
    assert effect.fps == 20.0


def test_sunset_custom_parameters():
    """Test EffectSunset with custom parameters."""
    effect = EffectSunset(
        power_on=True,
        duration=120,
        brightness=0.8,
        power_off=False,
        origin="center",
    )

    assert effect.duration == 120
    assert effect.brightness == 0.8
    assert effect.power_on is True
    assert effect.power_off is False
    assert effect.origin == "center"


def test_sunset_invalid_duration():
    """Test EffectSunset with invalid duration raises ValueError."""
    with pytest.raises(ValueError, match="Duration must be positive"):
        EffectSunset(duration=0)


def test_sunset_invalid_brightness():
    """Test EffectSunset with invalid brightness raises ValueError."""
    with pytest.raises(ValueError, match="Brightness must be 0.0-1.0"):
        EffectSunset(brightness=1.5)


def test_sunset_invalid_origin():
    """Test EffectSunset with invalid origin raises ValueError."""
    with pytest.raises(ValueError, match="Origin must be 'bottom' or 'center'"):
        EffectSunset(origin="left")  # type: ignore[arg-type]


class TestSunsetGenerateFrame:
    """Tests for EffectSunset.generate_frame()."""

    def test_start_is_bright(self) -> None:
        """Test that start of sunset (elapsed=0) is bright (day)."""
        effect = EffectSunset(duration=60, brightness=1.0)
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=64,
            canvas_width=8,
            canvas_height=8,
        )
        colors = effect.generate_frame(ctx)

        avg_brightness = sum(c.brightness for c in colors) / len(colors)
        assert avg_brightness > 0.3

    def test_end_is_dark(self) -> None:
        """Test that end of sunset (elapsed=duration) is dark (night)."""
        effect = EffectSunset(duration=60)
        ctx = FrameContext(
            elapsed_s=60.0,
            device_index=0,
            pixel_count=64,
            canvas_width=8,
            canvas_height=8,
        )
        colors = effect.generate_frame(ctx)

        avg_brightness = sum(c.brightness for c in colors) / len(colors)
        assert avg_brightness < 0.2

    def test_midpoint_golden_hour(self) -> None:
        """Test midpoint has warm hues (golden hour)."""
        effect = EffectSunset(duration=60)
        ctx = FrameContext(
            elapsed_s=30.0,
            device_index=0,
            pixel_count=64,
            canvas_width=8,
            canvas_height=8,
        )
        colors = effect.generate_frame(ctx)

        hues = [c.hue for c in colors]
        warm_pixels = sum(1 for h in hues if h <= 60 or h >= 300)
        assert warm_pixels > 0


class TestSunsetCompatibility:
    """Tests for EffectSunset device compatibility."""

    @pytest.mark.asyncio
    async def test_compatible_with_matrix(self) -> None:
        """Test is_light_compatible returns True for matrix lights."""
        effect = EffectSunset()
        light = MagicMock()
        capabilities = MagicMock()
        capabilities.has_matrix = True
        light.capabilities = capabilities

        assert await effect.is_light_compatible(light) is True

    @pytest.mark.asyncio
    async def test_incompatible_with_non_matrix(self) -> None:
        """Test is_light_compatible returns False for non-matrix lights."""
        effect = EffectSunset()
        light = MagicMock()
        capabilities = MagicMock()
        capabilities.has_matrix = False
        light.capabilities = capabilities

        assert await effect.is_light_compatible(light) is False

    @pytest.mark.asyncio
    async def test_loads_capabilities_when_none(self) -> None:
        """Test is_light_compatible loads capabilities when None."""
        effect = EffectSunset()
        light = MagicMock()
        light.capabilities = None

        async def ensure_caps():
            caps = MagicMock()
            caps.has_matrix = True
            light.capabilities = caps

        light._ensure_capabilities = AsyncMock(side_effect=ensure_caps)

        assert await effect.is_light_compatible(light) is True
        light._ensure_capabilities.assert_called_once()


class TestSunsetPowerOff:
    """Tests for EffectSunset power-off behavior."""

    @pytest.mark.asyncio
    async def test_power_off_after_completion(self) -> None:
        """Test lights are powered off when sunset completes with power_off=True."""
        effect = EffectSunset(duration=0.1, power_off=True)

        animator = MagicMock()
        animator.pixel_count = 64
        animator.canvas_width = 8
        animator.canvas_height = 8
        animator.send_frame = MagicMock()
        effect._animators = [animator]

        light1 = MagicMock()
        light1.set_power = AsyncMock()
        light2 = MagicMock()
        light2.set_power = AsyncMock()
        effect.participants = [light1, light2]

        await asyncio.wait_for(effect.async_play(), timeout=2.0)

        light1.set_power.assert_called_once_with(False)
        light2.set_power.assert_called_once_with(False)

    @pytest.mark.asyncio
    async def test_no_power_off_when_disabled(self) -> None:
        """Test lights are NOT powered off when power_off=False."""
        effect = EffectSunset(duration=0.1, power_off=False)

        animator = MagicMock()
        animator.pixel_count = 64
        animator.canvas_width = 8
        animator.canvas_height = 8
        animator.send_frame = MagicMock()
        effect._animators = [animator]

        light = MagicMock()
        light.set_power = AsyncMock()
        effect.participants = [light]

        await asyncio.wait_for(effect.async_play(), timeout=2.0)

        light.set_power.assert_not_called()


@pytest.mark.asyncio
async def test_sunset_from_poweroff():
    """Test from_poweroff_hsbk returns warm daylight."""
    effect = EffectSunset(brightness=0.8)
    light = MagicMock()
    result = await effect.from_poweroff_hsbk(light)

    assert result.hue == 60
    assert result.saturation == 0.2
    assert result.brightness == 0.8
    assert result.kelvin == KELVIN_COOL


def test_sunset_restore_on_complete_with_power_off():
    """Test sunset skips state restoration when power_off=True."""
    effect = EffectSunset(power_off=True)
    assert effect.restore_on_complete is False


def test_sunset_restore_on_complete_without_power_off():
    """Test sunset restores state when power_off=False."""
    effect = EffectSunset(power_off=False)
    assert effect.restore_on_complete is True


def test_sunset_inherit_prestate():
    """Test inherit_prestate returns True for EffectSunset."""
    effect = EffectSunset()
    assert effect.inherit_prestate(EffectSunset()) is True
    assert effect.inherit_prestate(EffectSunrise()) is False
    assert effect.inherit_prestate(MagicMock()) is False


def test_sunset_repr():
    """Test EffectSunset string representation."""
    effect = EffectSunset(duration=120, brightness=0.8, power_off=False)
    repr_str = repr(effect)

    assert "EffectSunset" in repr_str
    assert "duration=120" in repr_str
    assert "brightness=0.8" in repr_str
    assert "power_off=False" in repr_str
    assert "origin='bottom'" in repr_str


def test_sunset_repr_center_origin():
    """Test EffectSunset repr with center origin."""
    effect = EffectSunset(duration=60, origin="center")
    repr_str = repr(effect)

    assert "origin='center'" in repr_str


class TestSunsetCenterOrigin:
    """Tests for EffectSunset with center origin."""

    def test_start_is_bright_from_center(self) -> None:
        """Test center-origin sunset starts bright at center."""
        effect = EffectSunset(duration=60, brightness=1.0, origin="center")
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=64,
            canvas_width=8,
            canvas_height=8,
        )
        colors = effect.generate_frame(ctx)

        avg_brightness = sum(c.brightness for c in colors) / len(colors)
        assert avg_brightness > 0.3

    def test_center_contracts_symmetrically(self) -> None:
        """Test sunset contracts symmetrically toward center."""
        effect = EffectSunset(duration=60, origin="center")
        ctx = FrameContext(
            elapsed_s=36.0,  # 60% through — corners should be darker
            device_index=0,
            pixel_count=64,
            canvas_width=8,
            canvas_height=8,
        )
        colors = effect.generate_frame(ctx)

        # All four corners should have roughly equal brightness
        corners = [colors[0], colors[7], colors[7 * 8], colors[7 * 8 + 7]]
        corner_b = [c.brightness for c in corners]
        assert max(corner_b) - min(corner_b) < 0.05
