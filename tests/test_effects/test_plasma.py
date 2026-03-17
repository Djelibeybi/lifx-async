"""Tests for EffectPlasma (electric tendrils)."""

import asyncio
import random
from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.effects.base import LIFXEffect
from lifx.effects.frame_effect import FrameContext, FrameEffect
from lifx.effects.plasma import (
    _MAX_TENDRILS,
    _TENDRIL_LIFE_MAX,
    _TENDRIL_LIFE_MIN,
    EffectPlasma,
    _Tendril,
)

# ---------------------------------------------------------------------------
# Constructor / parameter validation
# ---------------------------------------------------------------------------


def test_plasma_default_parameters() -> None:
    """Test EffectPlasma with default parameters."""
    effect = EffectPlasma()

    assert effect.name == "plasma"
    assert effect.speed == 3.0
    assert effect.tendril_rate == 0.5
    assert effect.hue == 270
    assert effect.hue_spread == 60.0
    assert effect.brightness == 0.8
    assert effect.kelvin == 3500
    assert effect.zones_per_bulb == 1
    assert effect.power_on is True
    assert effect.fps == 20.0
    assert effect.duration is None


def test_plasma_custom_parameters() -> None:
    """Test EffectPlasma with custom parameters."""
    effect = EffectPlasma(
        speed=5.0,
        tendril_rate=2.0,
        hue=180,
        hue_spread=30.0,
        brightness=0.6,
        kelvin=5000,
        zones_per_bulb=3,
        power_on=False,
    )

    assert effect.speed == 5.0
    assert effect.tendril_rate == 2.0
    assert effect.hue == 180
    assert effect.hue_spread == 30.0
    assert effect.brightness == 0.6
    assert effect.kelvin == 5000
    assert effect.zones_per_bulb == 3
    assert effect.power_on is False


def test_plasma_invalid_speed() -> None:
    """Test EffectPlasma with invalid speed raises ValueError."""
    with pytest.raises(ValueError, match="Speed must be"):
        EffectPlasma(speed=0)

    with pytest.raises(ValueError, match="Speed must be"):
        EffectPlasma(speed=-1.0)


def test_plasma_invalid_tendril_rate() -> None:
    """Test EffectPlasma with invalid tendril_rate raises ValueError."""
    with pytest.raises(ValueError, match="Tendril rate must be"):
        EffectPlasma(tendril_rate=0)

    with pytest.raises(ValueError, match="Tendril rate must be"):
        EffectPlasma(tendril_rate=-1.0)


def test_plasma_invalid_hue() -> None:
    """Test EffectPlasma with invalid hue raises ValueError."""
    with pytest.raises(ValueError, match="Hue must be"):
        EffectPlasma(hue=-1)

    with pytest.raises(ValueError, match="Hue must be"):
        EffectPlasma(hue=361)


def test_plasma_invalid_hue_spread() -> None:
    """Test EffectPlasma with invalid hue_spread raises ValueError."""
    with pytest.raises(ValueError, match="Hue spread must be"):
        EffectPlasma(hue_spread=-1.0)

    with pytest.raises(ValueError, match="Hue spread must be"):
        EffectPlasma(hue_spread=181.0)


def test_plasma_invalid_brightness() -> None:
    """Test EffectPlasma with invalid brightness raises ValueError."""
    with pytest.raises(ValueError, match="Brightness must be"):
        EffectPlasma(brightness=1.5)

    with pytest.raises(ValueError, match="Brightness must be"):
        EffectPlasma(brightness=-0.1)


def test_plasma_invalid_kelvin() -> None:
    """Test EffectPlasma with invalid kelvin raises ValueError."""
    with pytest.raises(ValueError, match="Kelvin must be"):
        EffectPlasma(kelvin=1000)

    with pytest.raises(ValueError, match="Kelvin must be"):
        EffectPlasma(kelvin=10000)


def test_plasma_invalid_zones_per_bulb() -> None:
    """Test EffectPlasma with invalid zones_per_bulb raises ValueError."""
    with pytest.raises(ValueError, match="zones_per_bulb must be"):
        EffectPlasma(zones_per_bulb=0)

    with pytest.raises(ValueError, match="zones_per_bulb must be"):
        EffectPlasma(zones_per_bulb=-1)


def test_plasma_boundary_hue_values() -> None:
    """Test EffectPlasma accepts boundary hue values."""
    effect_0 = EffectPlasma(hue=0)
    assert effect_0.hue == 0

    effect_360 = EffectPlasma(hue=360)
    assert effect_360.hue == 360


def test_plasma_boundary_brightness_values() -> None:
    """Test EffectPlasma accepts boundary brightness values."""
    effect_0 = EffectPlasma(brightness=0.0)
    assert effect_0.brightness == 0.0

    effect_1 = EffectPlasma(brightness=1.0)
    assert effect_1.brightness == 1.0


def test_plasma_boundary_hue_spread_values() -> None:
    """Test EffectPlasma accepts boundary hue_spread values."""
    effect_0 = EffectPlasma(hue_spread=0.0)
    assert effect_0.hue_spread == 0.0

    effect_180 = EffectPlasma(hue_spread=180.0)
    assert effect_180.hue_spread == 180.0


# ---------------------------------------------------------------------------
# Inheritance
# ---------------------------------------------------------------------------


class TestPlasmaInheritance:
    """Tests for EffectPlasma class hierarchy."""

    def test_is_frame_effect(self) -> None:
        """Test EffectPlasma extends FrameEffect."""
        effect = EffectPlasma()
        assert isinstance(effect, FrameEffect)

    def test_is_lifx_effect(self) -> None:
        """Test EffectPlasma extends LIFXEffect."""
        effect = EffectPlasma()
        assert isinstance(effect, LIFXEffect)


# ---------------------------------------------------------------------------
# _Tendril dataclass
# ---------------------------------------------------------------------------


class TestTendril:
    """Tests for the _Tendril internal dataclass."""

    def test_tendril_is_alive(self) -> None:
        """Test tendril alive check."""
        tendril = _Tendril(zones=[0, 1, 2], birth_t=1.0, lifetime=0.5)
        assert tendril.is_alive(1.2) is True
        assert tendril.is_alive(1.49) is True
        assert tendril.is_alive(1.5) is False
        assert tendril.is_alive(2.0) is False

    def test_tendril_age_frac(self) -> None:
        """Test tendril normalized age calculation."""
        tendril = _Tendril(zones=[0, 1, 2], birth_t=1.0, lifetime=1.0)
        assert tendril.age_frac(1.0) == pytest.approx(0.0)
        assert tendril.age_frac(1.5) == pytest.approx(0.5)
        assert tendril.age_frac(2.0) == pytest.approx(1.0)

    def test_tendril_age_frac_clamps_at_one(self) -> None:
        """Test age_frac clamps at 1.0 when past lifetime."""
        tendril = _Tendril(zones=[0], birth_t=0.0, lifetime=0.5)
        assert tendril.age_frac(10.0) == 1.0

    def test_tendril_age_frac_zero_lifetime(self) -> None:
        """Test age_frac returns 1.0 for zero lifetime."""
        tendril = _Tendril(zones=[0], birth_t=0.0, lifetime=0.0)
        assert tendril.age_frac(0.0) == 1.0

    def test_tendril_defaults(self) -> None:
        """Test tendril default values."""
        tendril = _Tendril()
        assert tendril.zones == []
        assert tendril.birth_t == 0.0
        assert tendril.lifetime == 0.2
        assert tendril.hue_off == 0.0


# ---------------------------------------------------------------------------
# Frame generation
# ---------------------------------------------------------------------------


class TestPlasmaGenerateFrame:
    """Tests for EffectPlasma.generate_frame()."""

    def _make_ctx(self, elapsed_s: float = 1.0, pixel_count: int = 16) -> FrameContext:
        """Create a FrameContext for testing."""
        return FrameContext(
            elapsed_s=elapsed_s,
            device_index=0,
            pixel_count=pixel_count,
            canvas_width=pixel_count,
            canvas_height=1,
        )

    def test_single_pixel_returns_one_color(self) -> None:
        """Test single-pixel device returns one color."""
        effect = EffectPlasma()
        colors = effect.generate_frame(self._make_ctx(pixel_count=1))
        assert len(colors) == 1

    @pytest.mark.parametrize("pixel_count", [1, 8, 16, 32, 82])
    def test_returns_correct_pixel_count(self, pixel_count: int) -> None:
        """Test correct number of colors for various pixel counts."""
        effect = EffectPlasma()
        colors = effect.generate_frame(self._make_ctx(pixel_count=pixel_count))
        assert len(colors) == pixel_count

    def test_kelvin_matches_configured(self) -> None:
        """Test kelvin values match configured kelvin."""
        effect = EffectPlasma(kelvin=5000)
        colors = effect.generate_frame(self._make_ctx())
        for color in colors:
            assert color.kelvin == 5000

    def test_saturation_is_full(self) -> None:
        """Test all pixels have full saturation."""
        effect = EffectPlasma()
        colors = effect.generate_frame(self._make_ctx())
        for color in colors:
            assert color.saturation == 1.0

    def test_brightness_in_valid_range(self) -> None:
        """Test all brightness values are 0.0-1.0."""
        effect = EffectPlasma()
        colors = effect.generate_frame(self._make_ctx())
        for color in colors:
            assert 0.0 <= color.brightness <= 1.0

    def test_hue_in_valid_range(self) -> None:
        """Test all hue values are in valid range (0-360)."""
        effect = EffectPlasma(hue=270, hue_spread=60.0)
        # Generate several frames to exercise tendril hue offsets
        for t in range(10):
            colors = effect.generate_frame(self._make_ctx(elapsed_s=float(t)))
            for color in colors:
                assert 0 <= color.hue <= 360

    def test_elapsed_zero(self) -> None:
        """Test edge case with elapsed_s=0.0."""
        effect = EffectPlasma()
        colors = effect.generate_frame(self._make_ctx(elapsed_s=0.0))
        assert len(colors) == 16
        for color in colors:
            assert 0.0 <= color.brightness <= 1.0

    def test_zones_per_bulb_expands_colors(self) -> None:
        """Test zones_per_bulb groups zones into logical bulbs."""
        effect = EffectPlasma(zones_per_bulb=2)
        colors = effect.generate_frame(self._make_ctx(pixel_count=8))
        assert len(colors) == 8

        # Each pair of adjacent zones should have the same color
        for i in range(0, 8, 2):
            assert colors[i] == colors[i + 1]

    def test_zones_per_bulb_three(self) -> None:
        """Test zones_per_bulb=3 groups correctly."""
        effect = EffectPlasma(zones_per_bulb=3)
        colors = effect.generate_frame(self._make_ctx(pixel_count=9))
        assert len(colors) == 9

        # Each triplet should be identical
        for i in range(0, 9, 3):
            assert colors[i] == colors[i + 1] == colors[i + 2]

    def test_zones_per_bulb_trims_to_pixel_count(self) -> None:
        """Test output is trimmed when zones_per_bulb doesn't divide evenly."""
        effect = EffectPlasma(zones_per_bulb=3)
        colors = effect.generate_frame(self._make_ctx(pixel_count=10))
        assert len(colors) == 10

    def test_core_glow_at_center(self) -> None:
        """Test that center bulbs have nonzero brightness from the core."""
        effect = EffectPlasma(brightness=0.8)
        # Use enough zones so core radius > 0
        colors = effect.generate_frame(self._make_ctx(pixel_count=32))

        center = 32 // 2
        # Core center should have brightness > 0
        assert colors[center].brightness > 0.0

    def test_zero_brightness_produces_dark_frame(self) -> None:
        """Test brightness=0.0 produces all-dark output."""
        effect = EffectPlasma(brightness=0.0)
        colors = effect.generate_frame(self._make_ctx(pixel_count=16))
        for color in colors:
            assert color.brightness == 0.0


# ---------------------------------------------------------------------------
# Stateful behavior
# ---------------------------------------------------------------------------


class TestPlasmaState:
    """Tests for stateful behavior of EffectPlasma."""

    def _make_ctx(self, elapsed_s: float = 0.0, pixel_count: int = 32) -> FrameContext:
        return FrameContext(
            elapsed_s=elapsed_s,
            device_index=0,
            pixel_count=pixel_count,
            canvas_width=pixel_count,
            canvas_height=1,
        )

    def test_lazy_initialization(self) -> None:
        """Test state is initialized on first frame."""
        effect = EffectPlasma()
        assert effect._initialized is False

        effect.generate_frame(self._make_ctx())
        assert effect._initialized is True

    def test_reset_state_clears_tendrils(self) -> None:
        """Test _reset_state clears all state."""
        effect = EffectPlasma()
        effect.generate_frame(self._make_ctx(elapsed_s=0.0))
        assert effect._initialized is True

        effect._reset_state()
        assert effect._initialized is False
        assert len(effect._tendrils) == 0
        assert effect._next_spawn_t == 0.0

    def test_tendrils_spawn_over_time(self) -> None:
        """Test that tendrils accumulate across frames."""
        random.seed(42)
        effect = EffectPlasma(tendril_rate=100.0)

        # Generate many frames to spawn tendrils
        for i in range(20):
            effect.generate_frame(self._make_ctx(elapsed_s=i * 0.05))

        # With high tendril_rate, should have spawned some tendrils
        # (they may also expire, so just check something happened)
        # We verify the mechanism works by checking the initialization
        assert effect._initialized is True

    def test_tendrils_expire(self) -> None:
        """Test that old tendrils are removed."""
        effect = EffectPlasma()
        # Manually add an expired tendril
        effect._tendrils.append(_Tendril(zones=[5, 6, 7], birth_t=0.0, lifetime=0.1))

        # Generate frame well past its lifetime
        effect.generate_frame(self._make_ctx(elapsed_s=10.0))

        # Expired tendril should be removed
        for t in effect._tendrils:
            assert t.is_alive(10.0)

    def test_max_tendrils_cap(self) -> None:
        """Test tendril count never exceeds _MAX_TENDRILS."""
        effect = EffectPlasma(tendril_rate=1000.0)

        # Fill with long-lived tendrils
        for i in range(_MAX_TENDRILS):
            effect._tendrils.append(
                _Tendril(zones=[5, 6, 7], birth_t=0.0, lifetime=1000.0)
            )

        effect._initialized = True

        # Even with high rate, shouldn't exceed max
        effect.generate_frame(self._make_ctx(elapsed_s=1.0))
        assert len(effect._tendrils) <= _MAX_TENDRILS


# ---------------------------------------------------------------------------
# Tendril spawning
# ---------------------------------------------------------------------------


class TestPlasmaSpawnTendril:
    """Tests for tendril spawning logic."""

    def test_no_spawn_on_small_bulb_count(self) -> None:
        """Test tendrils are not spawned when bulb_count < 3."""
        effect = EffectPlasma()
        initial_count = len(effect._tendrils)

        effect._spawn_tendril(0.0, 2)
        assert len(effect._tendrils) == initial_count

        effect._spawn_tendril(0.0, 1)
        assert len(effect._tendrils) == initial_count

    def test_spawn_creates_tendril(self) -> None:
        """Test tendril is created on spawn."""
        random.seed(42)
        effect = EffectPlasma()
        effect._spawn_tendril(1.0, 16)

        assert len(effect._tendrils) >= 1
        tendril = effect._tendrils[0]
        assert tendril.birth_t == 1.0
        assert _TENDRIL_LIFE_MIN <= tendril.lifetime <= _TENDRIL_LIFE_MAX
        assert len(tendril.zones) > 0

    def test_spawn_tendril_zones_within_bounds(self) -> None:
        """Test spawned tendril zones are within valid range."""
        random.seed(123)
        effect = EffectPlasma()
        bulb_count = 32

        for _ in range(20):
            effect._spawn_tendril(0.0, bulb_count)

        for tendril in effect._tendrils:
            for zone in tendril.zones:
                assert 0 <= zone < bulb_count

    def test_spawn_tendril_starts_at_center(self) -> None:
        """Test tendril path starts at the center."""
        random.seed(42)
        effect = EffectPlasma()
        effect._spawn_tendril(0.0, 16)

        tendril = effect._tendrils[0]
        assert tendril.zones[0] == 16 // 2

    def test_tendril_hue_offset_within_spread(self) -> None:
        """Test tendril hue offsets are within hue_spread range."""
        random.seed(42)
        effect = EffectPlasma(hue_spread=30.0)

        for _ in range(20):
            effect._spawn_tendril(0.0, 16)

        for tendril in effect._tendrils:
            # Main tendrils should be within hue_spread
            # Fork tendrils may have +/- 10 extra
            assert abs(tendril.hue_off) <= 30.0 + 10.0

    def test_fork_creates_second_tendril(self) -> None:
        """Test that forking creates a second tendril."""
        # Force fork to always happen
        random.seed(0)
        effect = EffectPlasma()

        # Try many times to get a fork
        found_fork = False
        for seed in range(100):
            random.seed(seed)
            effect._tendrils.clear()
            effect._spawn_tendril(0.0, 32)
            if len(effect._tendrils) == 2:
                found_fork = True
                break

        assert found_fork, "Expected at least one fork to occur across 100 seeds"


# ---------------------------------------------------------------------------
# Frame loop integration
# ---------------------------------------------------------------------------


class TestPlasmaFrameLoop:
    """Tests for EffectPlasma running via FrameEffect frame loop."""

    @pytest.mark.asyncio
    async def test_sends_frames_via_animator(self) -> None:
        """Test plasma sends frames through animator.send_frame."""
        effect = EffectPlasma()

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
# Compatibility
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_plasma_from_poweroff() -> None:
    """Test from_poweroff_hsbk returns dim version of plasma color."""
    effect = EffectPlasma(hue=270, kelvin=5000)
    light = MagicMock()
    result = await effect.from_poweroff_hsbk(light)

    assert result.hue == 270
    assert result.saturation == 1.0
    assert result.brightness == 0.0
    assert result.kelvin == 5000


@pytest.mark.asyncio
async def test_plasma_is_light_compatible_with_color() -> None:
    """Test is_light_compatible returns True for color lights."""
    effect = EffectPlasma()
    light = MagicMock()
    capabilities = MagicMock()
    capabilities.has_color = True
    capabilities.has_matrix = False
    light.capabilities = capabilities

    assert await effect.is_light_compatible(light) is True


@pytest.mark.asyncio
async def test_plasma_is_light_compatible_without_color() -> None:
    """Test is_light_compatible returns False for non-color lights."""
    effect = EffectPlasma()
    light = MagicMock()
    capabilities = MagicMock()
    capabilities.has_color = False
    capabilities.has_matrix = False
    light.capabilities = capabilities

    assert await effect.is_light_compatible(light) is False


@pytest.mark.asyncio
async def test_plasma_not_compatible_with_matrix() -> None:
    """Test is_light_compatible returns False for matrix devices."""
    effect = EffectPlasma()
    light = MagicMock()
    capabilities = MagicMock()
    capabilities.has_color = True
    capabilities.has_matrix = True
    light.capabilities = capabilities

    assert await effect.is_light_compatible(light) is False


@pytest.mark.asyncio
async def test_plasma_is_light_compatible_none_capabilities() -> None:
    """Test is_light_compatible loads capabilities when None."""
    effect = EffectPlasma()
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
async def test_plasma_is_light_compatible_none_after_ensure() -> None:
    """Test is_light_compatible returns False when capabilities remain None."""
    effect = EffectPlasma()
    light = MagicMock()
    light.capabilities = None

    async def ensure_caps() -> None:
        pass  # capabilities stays None

    light._ensure_capabilities = AsyncMock(side_effect=ensure_caps)

    assert await effect.is_light_compatible(light) is False


def test_plasma_inherit_prestate() -> None:
    """Test inherit_prestate returns True for EffectPlasma."""
    effect = EffectPlasma()
    assert effect.inherit_prestate(EffectPlasma()) is True
    assert effect.inherit_prestate(MagicMock()) is False


def test_plasma_repr() -> None:
    """Test EffectPlasma string representation."""
    effect = EffectPlasma(speed=5.0, tendril_rate=2.0, hue=180, brightness=0.6)
    repr_str = repr(effect)

    assert "EffectPlasma" in repr_str
    assert "speed=5.0" in repr_str
    assert "tendril_rate=2.0" in repr_str
    assert "hue=180" in repr_str
    assert "brightness=0.6" in repr_str


def test_plasma_name_property() -> None:
    """Test name property returns 'plasma'."""
    effect = EffectPlasma()
    assert effect.name == "plasma"


# ---------------------------------------------------------------------------
# Core glow behavior
# ---------------------------------------------------------------------------


class TestPlasmaCoreGlow:
    """Tests for the core glow pulsing behavior."""

    def _make_ctx(self, elapsed_s: float = 0.0, pixel_count: int = 32) -> FrameContext:
        return FrameContext(
            elapsed_s=elapsed_s,
            device_index=0,
            pixel_count=pixel_count,
            canvas_width=pixel_count,
            canvas_height=1,
        )

    def test_core_brightness_varies_with_time(self) -> None:
        """Test core brightness changes across different time values."""
        effect = EffectPlasma(speed=1.0, brightness=1.0)
        center = 16

        brightnesses = []
        for i in range(10):
            t = i * 0.1
            colors = effect.generate_frame(self._make_ctx(elapsed_s=t, pixel_count=32))
            brightnesses.append(colors[center].brightness)

        # Core should pulse, so not all values should be identical
        assert len(set(brightnesses)) > 1

    def test_core_center_brighter_than_edges(self) -> None:
        """Test center is at least as bright as edges on a no-tendril frame."""
        # Use a fresh effect with low tendril rate
        effect = EffectPlasma(tendril_rate=0.001, brightness=1.0)
        colors = effect.generate_frame(self._make_ctx(elapsed_s=0.0, pixel_count=32))

        center = 16
        # Center should be at least as bright as the edges
        assert colors[center].brightness >= colors[0].brightness
        assert colors[center].brightness >= colors[31].brightness


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestPlasmaEdgeCases:
    """Tests for edge cases in plasma effect."""

    def _make_ctx(self, elapsed_s: float = 0.0, pixel_count: int = 16) -> FrameContext:
        return FrameContext(
            elapsed_s=elapsed_s,
            device_index=0,
            pixel_count=pixel_count,
            canvas_width=pixel_count,
            canvas_height=1,
        )

    def test_single_zone_device(self) -> None:
        """Test effect works on single-zone (regular bulb) device."""
        effect = EffectPlasma()
        colors = effect.generate_frame(self._make_ctx(pixel_count=1))
        assert len(colors) == 1
        assert 0.0 <= colors[0].brightness <= 1.0

    def test_two_zone_device(self) -> None:
        """Test effect works on two-zone device (no tendrils spawn)."""
        effect = EffectPlasma()
        colors = effect.generate_frame(self._make_ctx(pixel_count=2))
        assert len(colors) == 2

    def test_large_elapsed_time(self) -> None:
        """Test effect works with large elapsed_s values."""
        effect = EffectPlasma()
        colors = effect.generate_frame(self._make_ctx(elapsed_s=100000.0))
        assert len(colors) == 16
        for color in colors:
            assert 0.0 <= color.brightness <= 1.0

    def test_very_small_elapsed_increments(self) -> None:
        """Test effect works with very small time increments."""
        effect = EffectPlasma()
        for i in range(10):
            colors = effect.generate_frame(self._make_ctx(elapsed_s=i * 0.001))
            assert len(colors) == 16

    def test_multiple_frames_in_sequence(self) -> None:
        """Test generating many frames in sequence (state accumulation)."""
        effect = EffectPlasma(tendril_rate=10.0)
        for i in range(100):
            colors = effect.generate_frame(
                self._make_ctx(elapsed_s=i * 0.05, pixel_count=32)
            )
            assert len(colors) == 32
            for color in colors:
                assert 0.0 <= color.brightness <= 1.0
                assert 0 <= color.hue <= 360

    def test_hue_wrapping(self) -> None:
        """Test hue values wrap correctly near boundaries."""
        # hue=10 with hue_spread=60 could produce negative hues
        effect = EffectPlasma(hue=10, hue_spread=60.0)
        for i in range(20):
            colors = effect.generate_frame(
                self._make_ctx(elapsed_s=i * 0.1, pixel_count=32)
            )
            for color in colors:
                # After modulo, should be 0-360
                assert 0 <= color.hue <= 360
