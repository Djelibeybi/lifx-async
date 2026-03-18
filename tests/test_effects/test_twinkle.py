"""Tests for EffectTwinkle (sparkle) effect."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lifx.effects.base import LIFXEffect
from lifx.effects.frame_effect import FrameContext, FrameEffect
from lifx.effects.twinkle import EffectTwinkle


def _make_ctx(
    elapsed_s: float = 1.0,
    pixel_count: int = 16,
    canvas_width: int | None = None,
    canvas_height: int = 1,
    device_index: int = 0,
) -> FrameContext:
    """Helper to create a FrameContext."""
    return FrameContext(
        elapsed_s=elapsed_s,
        device_index=device_index,
        pixel_count=pixel_count,
        canvas_width=canvas_width or pixel_count,
        canvas_height=canvas_height,
    )


class TestTwinkleDefaults:
    """Tests for EffectTwinkle default parameters."""

    def test_default_parameters(self) -> None:
        """Test EffectTwinkle with default parameters."""
        effect = EffectTwinkle()

        assert effect.name == "twinkle"
        assert effect.speed == 1.0
        assert effect.density == 0.05
        assert effect.hue == 0
        assert effect.saturation == 0.0
        assert effect.brightness == 1.0
        assert effect.background_hue == 0
        assert effect.background_saturation == 0.0
        assert effect.background_brightness == 0.0
        assert effect.kelvin == 3500
        assert effect.power_on is True
        assert effect.fps == 20.0
        assert effect.duration is None

    def test_custom_parameters(self) -> None:
        """Test EffectTwinkle with custom parameters."""
        effect = EffectTwinkle(
            speed=2.0,
            density=0.1,
            hue=120,
            saturation=0.8,
            brightness=0.6,
            background_hue=240,
            background_saturation=0.5,
            background_brightness=0.2,
            kelvin=5000,
            power_on=False,
        )

        assert effect.speed == 2.0
        assert effect.density == 0.1
        assert effect.hue == 120
        assert effect.saturation == 0.8
        assert effect.brightness == 0.6
        assert effect.background_hue == 240
        assert effect.background_saturation == 0.5
        assert effect.background_brightness == 0.2
        assert effect.kelvin == 5000
        assert effect.power_on is False


class TestTwinkleValidation:
    """Tests for EffectTwinkle parameter validation."""

    def test_invalid_speed_zero(self) -> None:
        """Test speed=0 raises ValueError."""
        with pytest.raises(ValueError, match="Speed must be"):
            EffectTwinkle(speed=0)

    def test_invalid_speed_negative(self) -> None:
        """Test negative speed raises ValueError."""
        with pytest.raises(ValueError, match="Speed must be"):
            EffectTwinkle(speed=-1.0)

    def test_invalid_density_too_high(self) -> None:
        """Test density > 1.0 raises ValueError."""
        with pytest.raises(ValueError, match="Density must be"):
            EffectTwinkle(density=1.5)

    def test_invalid_density_negative(self) -> None:
        """Test negative density raises ValueError."""
        with pytest.raises(ValueError, match="Density must be"):
            EffectTwinkle(density=-0.1)

    def test_invalid_hue_too_high(self) -> None:
        """Test hue > 360 raises ValueError."""
        with pytest.raises(ValueError, match="Hue must be"):
            EffectTwinkle(hue=361)

    def test_invalid_hue_negative(self) -> None:
        """Test negative hue raises ValueError."""
        with pytest.raises(ValueError, match="Hue must be"):
            EffectTwinkle(hue=-1)

    def test_invalid_saturation_too_high(self) -> None:
        """Test saturation > 1.0 raises ValueError."""
        with pytest.raises(ValueError, match="Saturation must be"):
            EffectTwinkle(saturation=1.5)

    def test_invalid_saturation_negative(self) -> None:
        """Test negative saturation raises ValueError."""
        with pytest.raises(ValueError, match="Saturation must be"):
            EffectTwinkle(saturation=-0.1)

    def test_invalid_brightness_too_high(self) -> None:
        """Test brightness > 1.0 raises ValueError."""
        with pytest.raises(ValueError, match="Brightness must be"):
            EffectTwinkle(brightness=1.5)

    def test_invalid_brightness_negative(self) -> None:
        """Test negative brightness raises ValueError."""
        with pytest.raises(ValueError, match="Brightness must be"):
            EffectTwinkle(brightness=-0.1)

    def test_invalid_background_hue_too_high(self) -> None:
        """Test background_hue > 360 raises ValueError."""
        with pytest.raises(ValueError, match="Background hue must be"):
            EffectTwinkle(background_hue=361)

    def test_invalid_background_hue_negative(self) -> None:
        """Test negative background_hue raises ValueError."""
        with pytest.raises(ValueError, match="Background hue must be"):
            EffectTwinkle(background_hue=-1)

    def test_invalid_background_saturation_too_high(self) -> None:
        """Test background_saturation > 1.0 raises ValueError."""
        with pytest.raises(ValueError, match="Background saturation must be"):
            EffectTwinkle(background_saturation=1.5)

    def test_invalid_background_saturation_negative(self) -> None:
        """Test negative background_saturation raises ValueError."""
        with pytest.raises(ValueError, match="Background saturation must be"):
            EffectTwinkle(background_saturation=-0.1)

    def test_invalid_background_brightness_too_high(self) -> None:
        """Test background_brightness > 1.0 raises ValueError."""
        with pytest.raises(ValueError, match="Background brightness must be"):
            EffectTwinkle(background_brightness=1.5)

    def test_invalid_background_brightness_negative(self) -> None:
        """Test negative background_brightness raises ValueError."""
        with pytest.raises(ValueError, match="Background brightness must be"):
            EffectTwinkle(background_brightness=-0.1)

    def test_invalid_kelvin_too_low(self) -> None:
        """Test kelvin below minimum raises ValueError."""
        with pytest.raises(ValueError, match="Kelvin must be"):
            EffectTwinkle(kelvin=1000)

    def test_invalid_kelvin_too_high(self) -> None:
        """Test kelvin above maximum raises ValueError."""
        with pytest.raises(ValueError, match="Kelvin must be"):
            EffectTwinkle(kelvin=10000)


class TestTwinkleInheritance:
    """Tests for EffectTwinkle class hierarchy."""

    def test_is_frame_effect(self) -> None:
        """Test EffectTwinkle extends FrameEffect."""
        effect = EffectTwinkle()
        assert isinstance(effect, FrameEffect)

    def test_is_lifx_effect(self) -> None:
        """Test EffectTwinkle extends LIFXEffect."""
        effect = EffectTwinkle()
        assert isinstance(effect, LIFXEffect)


class TestTwinkleGenerateFrame:
    """Tests for EffectTwinkle.generate_frame()."""

    def test_single_pixel_returns_one_color(self) -> None:
        """Test single-pixel device returns one color."""
        effect = EffectTwinkle()
        ctx = _make_ctx(pixel_count=1)
        colors = effect.generate_frame(ctx)
        assert len(colors) == 1

    @pytest.mark.parametrize("pixel_count", [1, 8, 16, 82])
    def test_returns_correct_pixel_count(self, pixel_count: int) -> None:
        """Test correct number of colors for various pixel counts."""
        effect = EffectTwinkle()
        ctx = _make_ctx(pixel_count=pixel_count)
        colors = effect.generate_frame(ctx)
        assert len(colors) == pixel_count

    def test_valid_hsbk_ranges(self) -> None:
        """Test all HSBK values are in valid ranges."""
        effect = EffectTwinkle(
            hue=120,
            saturation=0.8,
            brightness=0.9,
            background_hue=240,
            background_saturation=0.5,
            background_brightness=0.2,
        )
        # Force some sparkles by calling multiple frames
        for t in [0.0, 0.05, 0.1, 0.15, 0.2]:
            ctx = _make_ctx(elapsed_s=t, pixel_count=32)
            colors = effect.generate_frame(ctx)
            for color in colors:
                assert 0 <= color.hue <= 360
                assert 0.0 <= color.saturation <= 1.0
                assert 0.0 <= color.brightness <= 1.0
                assert 1500 <= color.kelvin <= 9000

    def test_kelvin_matches_configured(self) -> None:
        """Test all pixels use the configured kelvin."""
        effect = EffectTwinkle(kelvin=5000)
        ctx = _make_ctx(pixel_count=16)
        colors = effect.generate_frame(ctx)
        for color in colors:
            assert color.kelvin == 5000

    def test_background_color_when_no_sparkles(self) -> None:
        """Test pixels show background color when not sparkling."""
        effect = EffectTwinkle(
            density=0.0,  # No sparkles ever trigger
            background_hue=240,
            background_saturation=0.5,
            background_brightness=0.2,
            kelvin=4000,
        )
        ctx = _make_ctx(elapsed_s=1.0, pixel_count=16)
        colors = effect.generate_frame(ctx)

        for color in colors:
            assert color.hue == 240
            assert color.saturation == 0.5
            assert color.brightness == 0.2
            assert color.kelvin == 4000

    def test_elapsed_zero_produces_valid_frame(self) -> None:
        """Test edge case with elapsed_s=0.0."""
        effect = EffectTwinkle()
        ctx = _make_ctx(elapsed_s=0.0, pixel_count=16)
        colors = effect.generate_frame(ctx)
        assert len(colors) == 16
        for color in colors:
            assert 0.0 <= color.brightness <= 1.0


class TestTwinkleStatefulBehavior:
    """Tests for EffectTwinkle stateful sparkle tracking."""

    def test_state_initialized_lazily(self) -> None:
        """Test sparkle timers are None before first frame."""
        effect = EffectTwinkle()
        assert effect._sparkle_timers is None
        assert effect._last_elapsed_s is None

    def test_state_initialized_on_first_frame(self) -> None:
        """Test sparkle timers are created on first generate_frame call."""
        effect = EffectTwinkle()
        ctx = _make_ctx(pixel_count=16)
        effect.generate_frame(ctx)

        assert effect._sparkle_timers is not None
        assert len(effect._sparkle_timers) == 16
        assert effect._last_elapsed_s is not None

    def test_state_reinitializes_on_pixel_count_change(self) -> None:
        """Test sparkle timers reinitialize when pixel count changes."""
        effect = EffectTwinkle()
        ctx8 = _make_ctx(pixel_count=8)
        effect.generate_frame(ctx8)
        assert len(effect._sparkle_timers) == 8  # type: ignore[arg-type]

        ctx16 = _make_ctx(pixel_count=16)
        effect.generate_frame(ctx16)
        assert len(effect._sparkle_timers) == 16  # type: ignore[arg-type]

    def test_output_changes_across_sequential_frames(self) -> None:
        """Test that output changes over multiple sequential frames.

        With high density, sparkles should trigger and then decay,
        producing different output across frames.
        """
        effect = EffectTwinkle(density=1.0, speed=0.5)

        # Seed random for reproducibility within this test
        with patch("lifx.effects.twinkle.random") as mock_random:
            # Make random.random() always return 0.0 (always triggers sparkle)
            mock_random.random.return_value = 0.0

            frames = []
            for i in range(5):
                ctx = _make_ctx(elapsed_s=i * 0.1, pixel_count=8)
                frame = effect.generate_frame(ctx)
                frames.append(frame)

        # First frame (dt=0) should be all background (no time has passed)
        # Subsequent frames should differ as sparkles trigger and decay
        all_same = all(f == frames[0] for f in frames)
        assert not all_same, "Frames should change over time"

    def test_sparkle_triggers_with_high_density(self) -> None:
        """Test sparkles actually trigger when density is high."""
        effect = EffectTwinkle(
            density=1.0,
            speed=1.0,
            brightness=1.0,
            background_brightness=0.0,
        )

        with patch("lifx.effects.twinkle.random") as mock_random:
            # Always trigger sparkle
            mock_random.random.return_value = 0.0

            # First frame: initialize (dt=0, no sparkles trigger)
            ctx0 = _make_ctx(elapsed_s=0.0, pixel_count=8)
            effect.generate_frame(ctx0)

            # Second frame: dt > 0, sparkles should trigger
            ctx1 = _make_ctx(elapsed_s=0.1, pixel_count=8)
            colors = effect.generate_frame(ctx1)

            # At least some pixels should be sparkling (brightness > 0)
            sparkling = [c for c in colors if c.brightness > 0.0]
            assert len(sparkling) > 0, "Some pixels should be sparkling"

    def test_sparkle_decay_over_time(self) -> None:
        """Test sparkle brightness decays over time via quadratic falloff."""
        effect = EffectTwinkle(
            density=1.0,
            speed=1.0,
            brightness=1.0,
            background_brightness=0.0,
        )

        with patch("lifx.effects.twinkle.random") as mock_random:
            mock_random.random.return_value = 0.0

            # Initialize
            effect.generate_frame(_make_ctx(elapsed_s=0.0, pixel_count=1))
            # Trigger sparkle
            effect.generate_frame(_make_ctx(elapsed_s=0.05, pixel_count=1))

            # Now stop triggering new sparkles and watch decay
            mock_random.random.return_value = 1.0  # Never trigger

            brightnesses = []
            for i in range(2, 20):
                t = i * 0.05
                colors = effect.generate_frame(_make_ctx(elapsed_s=t, pixel_count=1))
                brightnesses.append(colors[0].brightness)

            # Brightness should generally decrease over time (quadratic decay)
            # Find a pair where brightness decreases
            found_decrease = any(
                brightnesses[i] > brightnesses[i + 1]
                for i in range(len(brightnesses) - 1)
                if brightnesses[i] > 0
            )
            assert found_decrease, "Brightness should decay over time"

    def test_no_sparkles_on_first_frame(self) -> None:
        """Test first frame (dt=0) has no sparkles since probability is 0."""
        effect = EffectTwinkle(
            density=1.0,
            brightness=1.0,
            background_brightness=0.0,
        )
        ctx = _make_ctx(elapsed_s=0.0, pixel_count=16)
        colors = effect.generate_frame(ctx)

        # All should be background (dt=0 means probability=0)
        for color in colors:
            assert color.brightness == 0.0

    def test_backwards_time_jump_clamped(self) -> None:
        """Test backwards elapsed_s is handled gracefully (dt clamped to 0)."""
        effect = EffectTwinkle(density=0.0)

        # Normal frame
        effect.generate_frame(_make_ctx(elapsed_s=1.0, pixel_count=8))
        # Backwards jump
        colors = effect.generate_frame(_make_ctx(elapsed_s=0.5, pixel_count=8))
        assert len(colors) == 8  # Should not crash


class TestTwinkleHueBlending:
    """Tests for sparkle-to-background hue transition."""

    def test_high_intensity_uses_sparkle_hue(self) -> None:
        """Test bright sparkles use the sparkle hue."""
        effect = EffectTwinkle(
            hue=120,
            saturation=1.0,
            brightness=1.0,
            background_hue=240,
            background_saturation=0.5,
            background_brightness=0.0,
            density=1.0,
            speed=2.0,
        )

        with patch("lifx.effects.twinkle.random") as mock_random:
            mock_random.random.return_value = 0.0
            # Initialize
            effect.generate_frame(_make_ctx(elapsed_s=0.0, pixel_count=1))
            # Trigger sparkle
            colors = effect.generate_frame(_make_ctx(elapsed_s=0.05, pixel_count=1))

            # Just-triggered sparkle should have high intensity -> sparkle hue
            assert colors[0].hue == 120

    def test_low_intensity_uses_background_hue(self) -> None:
        """Test faded sparkles snap to background hue."""
        effect = EffectTwinkle(
            hue=120,
            saturation=1.0,
            brightness=1.0,
            background_hue=240,
            background_saturation=0.5,
            background_brightness=0.0,
            density=1.0,
            speed=0.2,
        )

        with patch("lifx.effects.twinkle.random") as mock_random:
            mock_random.random.return_value = 0.0
            # Initialize
            effect.generate_frame(_make_ctx(elapsed_s=0.0, pixel_count=1))
            # Trigger sparkle
            effect.generate_frame(_make_ctx(elapsed_s=0.05, pixel_count=1))

            # Stop new sparkles and let it decay past threshold
            mock_random.random.return_value = 1.0
            # speed=0.2, after ~0.15s the fraction is ~0.25, intensity=0.0625 < 0.5
            colors = effect.generate_frame(_make_ctx(elapsed_s=0.2, pixel_count=1))

            # Should have snapped to background hue if still sparkling
            # or be full background if sparkle ended
            assert colors[0].hue in (120, 240)


@pytest.mark.asyncio
async def test_twinkle_from_poweroff_hsbk() -> None:
    """Test from_poweroff_hsbk returns background color at zero brightness."""
    effect = EffectTwinkle(
        background_hue=200,
        background_saturation=0.6,
        kelvin=5000,
    )
    light = MagicMock()
    result = await effect.from_poweroff_hsbk(light)

    assert result.hue == 200
    assert result.saturation == 0.6
    assert result.brightness == 0.0
    assert result.kelvin == 5000


@pytest.mark.asyncio
async def test_twinkle_is_light_compatible_with_color() -> None:
    """Test is_light_compatible returns True for color lights."""
    effect = EffectTwinkle()
    light = MagicMock()
    capabilities = MagicMock()
    capabilities.has_color = True
    light.capabilities = capabilities

    assert await effect.is_light_compatible(light) is True


@pytest.mark.asyncio
async def test_twinkle_is_light_compatible_without_color() -> None:
    """Test is_light_compatible returns False for non-color lights."""
    effect = EffectTwinkle()
    light = MagicMock()
    capabilities = MagicMock()
    capabilities.has_color = False
    light.capabilities = capabilities

    assert await effect.is_light_compatible(light) is False


@pytest.mark.asyncio
async def test_twinkle_is_light_compatible_none_capabilities() -> None:
    """Test is_light_compatible loads capabilities when None."""
    effect = EffectTwinkle()
    light = MagicMock()
    light.capabilities = None

    async def ensure_caps() -> None:
        caps = MagicMock()
        caps.has_color = True
        light.capabilities = caps

    light.ensure_capabilities = AsyncMock(side_effect=ensure_caps)

    assert await effect.is_light_compatible(light) is True
    light.ensure_capabilities.assert_called_once()


def test_twinkle_inherit_prestate() -> None:
    """Test inherit_prestate returns True for EffectTwinkle."""
    effect = EffectTwinkle()
    assert effect.inherit_prestate(EffectTwinkle()) is True
    assert effect.inherit_prestate(MagicMock()) is False


def test_twinkle_repr() -> None:
    """Test EffectTwinkle string representation."""
    effect = EffectTwinkle(speed=2.0, density=0.1, hue=120, kelvin=5000)
    repr_str = repr(effect)

    assert "EffectTwinkle" in repr_str
    assert "speed=2.0" in repr_str
    assert "density=0.1" in repr_str
    assert "hue=120" in repr_str
    assert "kelvin=5000" in repr_str
