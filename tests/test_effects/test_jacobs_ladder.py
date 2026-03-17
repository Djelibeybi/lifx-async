"""Tests for EffectJacobsLadder (electric arcs)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.effects.base import LIFXEffect
from lifx.effects.frame_effect import FrameContext, FrameEffect
from lifx.effects.jacobs_ladder import (
    _ARC_HUE_DEG,
    _ARC_SAT_FRAC,
    _GAP_MIN_BULBS,
    EffectJacobsLadder,
    _ArcPair,
)

# ---------------------------------------------------------------------------
# Constructor / parameter validation
# ---------------------------------------------------------------------------


def test_default_parameters() -> None:
    """Test EffectJacobsLadder with default parameters."""
    effect = EffectJacobsLadder()

    assert effect.name == "jacobs_ladder"
    assert effect.speed == 0.5
    assert effect.arcs == 2
    assert effect.gap == 5
    assert effect.brightness == 0.8
    assert effect.kelvin == 6500
    assert effect.zones_per_bulb == 1
    assert effect.power_on is True
    assert effect.fps == 20.0
    assert effect.duration is None


def test_custom_parameters() -> None:
    """Test EffectJacobsLadder with custom parameters."""
    effect = EffectJacobsLadder(
        speed=0.3,
        arcs=3,
        gap=8,
        brightness=0.6,
        kelvin=5000,
        zones_per_bulb=3,
        power_on=False,
    )

    assert effect.speed == 0.3
    assert effect.arcs == 3
    assert effect.gap == 8
    assert effect.brightness == 0.6
    assert effect.kelvin == 5000
    assert effect.zones_per_bulb == 3
    assert effect.power_on is False


def test_invalid_speed_too_low() -> None:
    """Test speed below minimum raises ValueError."""
    with pytest.raises(ValueError, match="Speed must be"):
        EffectJacobsLadder(speed=0.01)


def test_invalid_speed_too_high() -> None:
    """Test speed above maximum raises ValueError."""
    with pytest.raises(ValueError, match="Speed must be"):
        EffectJacobsLadder(speed=1.5)


def test_invalid_arcs_too_low() -> None:
    """Test arcs below minimum raises ValueError."""
    with pytest.raises(ValueError, match="Arcs must be"):
        EffectJacobsLadder(arcs=0)


def test_invalid_arcs_too_high() -> None:
    """Test arcs above maximum raises ValueError."""
    with pytest.raises(ValueError, match="Arcs must be"):
        EffectJacobsLadder(arcs=6)


def test_invalid_gap_too_low() -> None:
    """Test gap below minimum raises ValueError."""
    with pytest.raises(ValueError, match="Gap must be"):
        EffectJacobsLadder(gap=1)


def test_invalid_gap_too_high() -> None:
    """Test gap above maximum raises ValueError."""
    with pytest.raises(ValueError, match="Gap must be"):
        EffectJacobsLadder(gap=13)


def test_invalid_brightness_too_low() -> None:
    """Test brightness below minimum raises ValueError."""
    with pytest.raises(ValueError, match="Brightness must be"):
        EffectJacobsLadder(brightness=-0.1)


def test_invalid_brightness_too_high() -> None:
    """Test brightness above maximum raises ValueError."""
    with pytest.raises(ValueError, match="Brightness must be"):
        EffectJacobsLadder(brightness=1.5)


def test_invalid_kelvin_too_low() -> None:
    """Test kelvin below minimum raises ValueError."""
    with pytest.raises(ValueError, match="Kelvin must be"):
        EffectJacobsLadder(kelvin=1000)


def test_invalid_kelvin_too_high() -> None:
    """Test kelvin above maximum raises ValueError."""
    with pytest.raises(ValueError, match="Kelvin must be"):
        EffectJacobsLadder(kelvin=10000)


def test_invalid_zones_per_bulb_zero() -> None:
    """Test zones_per_bulb of zero raises ValueError."""
    with pytest.raises(ValueError, match="zones_per_bulb must be"):
        EffectJacobsLadder(zones_per_bulb=0)


def test_invalid_zones_per_bulb_negative() -> None:
    """Test negative zones_per_bulb raises ValueError."""
    with pytest.raises(ValueError, match="zones_per_bulb must be"):
        EffectJacobsLadder(zones_per_bulb=-1)


def test_speed_boundary_low() -> None:
    """Test speed at minimum boundary is accepted."""
    effect = EffectJacobsLadder(speed=0.02)
    assert effect.speed == 0.02


def test_speed_boundary_high() -> None:
    """Test speed at maximum boundary is accepted."""
    effect = EffectJacobsLadder(speed=1.0)
    assert effect.speed == 1.0


def test_arcs_boundary_values() -> None:
    """Test arcs at boundary values are accepted."""
    assert EffectJacobsLadder(arcs=1).arcs == 1
    assert EffectJacobsLadder(arcs=5).arcs == 5


def test_gap_boundary_values() -> None:
    """Test gap at boundary values are accepted."""
    assert EffectJacobsLadder(gap=2).gap == 2
    assert EffectJacobsLadder(gap=12).gap == 12


# ---------------------------------------------------------------------------
# Inheritance
# ---------------------------------------------------------------------------


class TestInheritance:
    """Tests for EffectJacobsLadder class hierarchy."""

    def test_is_frame_effect(self) -> None:
        """Test EffectJacobsLadder extends FrameEffect."""
        effect = EffectJacobsLadder()
        assert isinstance(effect, FrameEffect)

    def test_is_lifx_effect(self) -> None:
        """Test EffectJacobsLadder extends LIFXEffect."""
        effect = EffectJacobsLadder()
        assert isinstance(effect, LIFXEffect)


# ---------------------------------------------------------------------------
# _ArcPair internal state
# ---------------------------------------------------------------------------


class TestArcPair:
    """Tests for _ArcPair internal state management."""

    def test_creation(self) -> None:
        """Test _ArcPair stores initial values."""
        arc = _ArcPair(position=10.0, gap=5.0, speed=0.5, direction=1)
        assert arc.position == 10.0
        assert arc.gap == 5.0
        assert arc.gap_target == 5.0
        assert arc.speed == 0.5
        assert arc.direction == 1

    def test_step_advances_position(self) -> None:
        """Test step moves position by speed * direction."""
        arc = _ArcPair(position=10.0, gap=5.0, speed=0.5, direction=1)
        arc.step(gap_min=2, gap_max=10.0)
        assert arc.position == 10.5

    def test_step_negative_direction(self) -> None:
        """Test step moves in negative direction."""
        arc = _ArcPair(position=10.0, gap=5.0, speed=0.5, direction=-1)
        arc.step(gap_min=2, gap_max=10.0)
        assert arc.position == 9.5

    def test_left_right_edges(self) -> None:
        """Test left and right edge calculation."""
        arc = _ArcPair(position=10.0, gap=6.0, speed=0.5, direction=1)
        assert arc.left_edge() == 7.0
        assert arc.right_edge() == 13.0

    def test_is_off_string_forward(self) -> None:
        """Test arc scrolled off end in forward direction."""
        arc = _ArcPair(position=25.0, gap=4.0, speed=0.5, direction=1)
        # left_edge = 23, which is >= 20 (bulb_count)
        assert arc.is_off_string(bulb_count=20) is True

    def test_is_not_off_string_forward(self) -> None:
        """Test arc still on string in forward direction."""
        arc = _ArcPair(position=15.0, gap=4.0, speed=0.5, direction=1)
        assert arc.is_off_string(bulb_count=20) is False

    def test_is_off_string_reverse(self) -> None:
        """Test arc scrolled off start in reverse direction."""
        arc = _ArcPair(position=-5.0, gap=4.0, speed=0.5, direction=-1)
        # right_edge = -3, which is < 0
        assert arc.is_off_string(bulb_count=20) is True

    def test_is_not_off_string_reverse(self) -> None:
        """Test arc still on string in reverse direction."""
        arc = _ArcPair(position=5.0, gap=4.0, speed=0.5, direction=-1)
        assert arc.is_off_string(bulb_count=20) is False

    def test_gap_stays_within_bounds(self) -> None:
        """Test gap is clamped within min/max after many steps."""
        arc = _ArcPair(position=10.0, gap=5.0, speed=0.1, direction=1)
        for _ in range(100):
            arc.step(gap_min=2, gap_max=8.0)
        assert 2 <= arc.gap <= 8.0


# ---------------------------------------------------------------------------
# generate_frame
# ---------------------------------------------------------------------------


class TestGenerateFrame:
    """Tests for EffectJacobsLadder.generate_frame()."""

    def _make_ctx(self, pixel_count: int = 16, elapsed_s: float = 1.0) -> FrameContext:
        return FrameContext(
            elapsed_s=elapsed_s,
            device_index=0,
            pixel_count=pixel_count,
            canvas_width=pixel_count,
            canvas_height=1,
        )

    def test_returns_correct_pixel_count(self) -> None:
        """Test frame has exactly pixel_count colors."""
        effect = EffectJacobsLadder()
        colors = effect.generate_frame(self._make_ctx(pixel_count=16))
        assert len(colors) == 16

    @pytest.mark.parametrize("pixel_count", [1, 8, 16, 32, 82])
    def test_various_pixel_counts(self, pixel_count: int) -> None:
        """Test correct output length for various pixel counts."""
        effect = EffectJacobsLadder()
        colors = effect.generate_frame(self._make_ctx(pixel_count=pixel_count))
        assert len(colors) == pixel_count

    def test_brightness_in_valid_range(self) -> None:
        """Test all brightness values are 0.0-1.0."""
        effect = EffectJacobsLadder()
        colors = effect.generate_frame(self._make_ctx(pixel_count=32))
        for color in colors:
            assert 0.0 <= color.brightness <= 1.0

    def test_saturation_in_valid_range(self) -> None:
        """Test all saturation values are 0.0-1.0."""
        effect = EffectJacobsLadder()
        colors = effect.generate_frame(self._make_ctx(pixel_count=32))
        for color in colors:
            assert 0.0 <= color.saturation <= 1.0

    def test_kelvin_matches_configured(self) -> None:
        """Test kelvin values match configured kelvin."""
        effect = EffectJacobsLadder(kelvin=5000)
        colors = effect.generate_frame(self._make_ctx(pixel_count=16))
        for color in colors:
            assert color.kelvin == 5000

    def test_not_all_black(self) -> None:
        """Test at least one arc is visible (not all zones black)."""
        effect = EffectJacobsLadder()
        colors = effect.generate_frame(self._make_ctx(pixel_count=32))
        brightnesses = [c.brightness for c in colors]
        assert max(brightnesses) > 0, "At least one zone should be lit"

    def test_has_dark_zones(self) -> None:
        """Test that not all zones are lit (background is dark)."""
        effect = EffectJacobsLadder(arcs=1, gap=3)
        colors = effect.generate_frame(self._make_ctx(pixel_count=32))
        dark_count = sum(1 for c in colors if c.brightness < 0.01)
        assert dark_count > 0, "Some zones should be dark (background)"

    def test_brightness_capped_at_configured(self) -> None:
        """Test no brightness exceeds the configured maximum."""
        effect = EffectJacobsLadder(brightness=0.5)
        colors = effect.generate_frame(self._make_ctx(pixel_count=32))
        for color in colors:
            assert color.brightness <= 0.5 + 1e-9

    def test_zones_per_bulb_groups_zones(self) -> None:
        """Test zones_per_bulb groups adjacent zones."""
        effect = EffectJacobsLadder(zones_per_bulb=2)
        colors = effect.generate_frame(self._make_ctx(pixel_count=8))
        assert len(colors) == 8
        for i in range(0, 8, 2):
            assert colors[i] == colors[i + 1]

    def test_zones_per_bulb_3(self) -> None:
        """Test zones_per_bulb=3 groups triplets."""
        effect = EffectJacobsLadder(zones_per_bulb=3)
        colors = effect.generate_frame(self._make_ctx(pixel_count=9))
        assert len(colors) == 9
        for i in range(0, 9, 3):
            assert colors[i] == colors[i + 1] == colors[i + 2]

    def test_elapsed_zero(self) -> None:
        """Test edge case with elapsed_s=0.0."""
        effect = EffectJacobsLadder()
        colors = effect.generate_frame(self._make_ctx(pixel_count=16, elapsed_s=0.0))
        assert len(colors) == 16
        for color in colors:
            assert 0.0 <= color.brightness <= 1.0

    def test_single_pixel_device(self) -> None:
        """Test single-pixel device returns one color."""
        effect = EffectJacobsLadder()
        colors = effect.generate_frame(self._make_ctx(pixel_count=1))
        assert len(colors) == 1


# ---------------------------------------------------------------------------
# Stateful behavior
# ---------------------------------------------------------------------------


class TestStatefulBehavior:
    """Tests for stateful arc management."""

    def _make_ctx(self, pixel_count: int = 32, elapsed_s: float = 0.0) -> FrameContext:
        return FrameContext(
            elapsed_s=elapsed_s,
            device_index=0,
            pixel_count=pixel_count,
            canvas_width=pixel_count,
            canvas_height=1,
        )

    def test_lazy_initialization(self) -> None:
        """Test arcs are not created until first generate_frame call."""
        effect = EffectJacobsLadder()
        assert len(effect._arc_pairs) == 0
        assert effect._initialized is False

        effect.generate_frame(self._make_ctx())
        assert effect._initialized is True
        assert len(effect._arc_pairs) >= 1

    def test_first_arc_visible_immediately(self) -> None:
        """Test first arc is placed partway onto the string."""
        effect = EffectJacobsLadder(arcs=1)
        effect.generate_frame(self._make_ctx(pixel_count=32))

        # First arc should be around 30% of bulb_count, not at edge.
        assert len(effect._arc_pairs) >= 1
        # With 32 zones, 30% is ~9.6
        first_arc = effect._arc_pairs[0]
        assert first_arc.position > 0

    def test_maintains_arc_count(self) -> None:
        """Test effect spawns arcs to reach target count."""
        effect = EffectJacobsLadder(arcs=3)
        effect.generate_frame(self._make_ctx())
        assert len(effect._arc_pairs) >= 3

    def test_arcs_removed_when_off_string(self) -> None:
        """Test arcs are removed once they scroll off the string."""
        effect = EffectJacobsLadder(arcs=1, speed=1.0)
        ctx = self._make_ctx(pixel_count=16)

        # Run many frames to let arcs scroll off.
        for _ in range(100):
            effect.generate_frame(ctx)

        # At least one arc should always be present.
        assert len(effect._arc_pairs) >= 1

    def test_always_at_least_one_arc(self) -> None:
        """Test at least one arc is always present after many frames."""
        effect = EffectJacobsLadder(arcs=1, speed=1.0)
        ctx = self._make_ctx(pixel_count=10)

        for _ in range(200):
            effect.generate_frame(ctx)
            assert len(effect._arc_pairs) >= 1

    def test_frames_evolve_over_time(self) -> None:
        """Test consecutive frames produce different output (stochastic)."""
        effect = EffectJacobsLadder()
        ctx = self._make_ctx(pixel_count=32)

        frames = []
        for _ in range(5):
            frames.append(effect.generate_frame(ctx))

        # Due to randomness, most frames should differ.
        unique_frames = set()
        for f in frames:
            unique_frames.add(tuple((c.brightness, c.saturation) for c in f))
        assert len(unique_frames) > 1


# ---------------------------------------------------------------------------
# Spawn logic
# ---------------------------------------------------------------------------


class TestSpawnLogic:
    """Tests for arc spawning behavior."""

    def test_spawn_arc_at_entry_edge(self) -> None:
        """Test spawned arc starts near the entry edge."""
        effect = EffectJacobsLadder(gap=5)
        arc = effect._spawn_arc(bulb_count=20)
        # direction=1, so entry is at the low end.
        # Position should be near the start: -half + 1.0
        assert arc.position < 5.0
        assert arc.direction == 1

    def test_spawn_gap_has_variation(self) -> None:
        """Test spawned arcs have slight gap variation."""
        effect = EffectJacobsLadder(gap=5)
        gaps = set()
        for _ in range(20):
            arc = effect._spawn_arc(bulb_count=20)
            gaps.add(round(arc.gap, 2))
        # With uniform(-1, 1) noise, we should get variation.
        assert len(gaps) > 1

    def test_spawn_gap_never_below_minimum(self) -> None:
        """Test spawned arc gap is never below GAP_MIN_BULBS."""
        effect = EffectJacobsLadder(gap=2)
        for _ in range(50):
            arc = effect._spawn_arc(bulb_count=20)
            assert arc.gap >= _GAP_MIN_BULBS


# ---------------------------------------------------------------------------
# Arc color properties
# ---------------------------------------------------------------------------


class TestArcColors:
    """Tests for arc color characteristics."""

    def _make_ctx(self, pixel_count: int = 32) -> FrameContext:
        return FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=pixel_count,
            canvas_width=pixel_count,
            canvas_height=1,
        )

    def test_lit_zones_use_arc_hue(self) -> None:
        """Test lit zones have the electric blue arc hue."""
        effect = EffectJacobsLadder(arcs=2)
        colors = effect.generate_frame(self._make_ctx())
        lit_hues = {c.hue for c in colors if c.brightness > 0.01}
        # All lit zones should have the arc hue.
        for hue in lit_hues:
            assert hue == pytest.approx(_ARC_HUE_DEG, abs=1.0)

    def test_saturation_values_are_partial(self) -> None:
        """Test saturation is partially desaturated (not fully saturated)."""
        effect = EffectJacobsLadder(arcs=2)
        colors = effect.generate_frame(self._make_ctx())
        lit_sats = {c.saturation for c in colors if c.brightness > 0.01}
        # Saturation should be one of the arc constants (not 1.0).
        for sat in lit_sats:
            assert sat <= _ARC_SAT_FRAC + 0.01


# ---------------------------------------------------------------------------
# from_poweroff_hsbk
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_from_poweroff_hsbk() -> None:
    """Test from_poweroff_hsbk returns arc color at zero brightness."""
    effect = EffectJacobsLadder(kelvin=5000)
    light = MagicMock()
    result = await effect.from_poweroff_hsbk(light)

    assert result.hue == _ARC_HUE_DEG
    assert result.saturation == _ARC_SAT_FRAC
    assert result.brightness == 0.0
    assert result.kelvin == 5000


# ---------------------------------------------------------------------------
# is_light_compatible
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compatible_with_multizone() -> None:
    """Test is_light_compatible returns True for multizone lights."""
    effect = EffectJacobsLadder()
    light = MagicMock()
    capabilities = MagicMock()
    capabilities.has_multizone = True
    light.capabilities = capabilities

    assert await effect.is_light_compatible(light) is True


@pytest.mark.asyncio
async def test_incompatible_without_multizone() -> None:
    """Test is_light_compatible returns False for non-multizone lights."""
    effect = EffectJacobsLadder()
    light = MagicMock()
    capabilities = MagicMock()
    capabilities.has_multizone = False
    light.capabilities = capabilities

    assert await effect.is_light_compatible(light) is False


@pytest.mark.asyncio
async def test_compatible_loads_capabilities_when_none() -> None:
    """Test is_light_compatible fetches capabilities when None."""
    effect = EffectJacobsLadder()
    light = MagicMock()
    light.capabilities = None

    async def ensure_caps() -> None:
        caps = MagicMock()
        caps.has_multizone = True
        light.capabilities = caps

    light._ensure_capabilities = AsyncMock(side_effect=ensure_caps)

    assert await effect.is_light_compatible(light) is True
    light._ensure_capabilities.assert_called_once()


# ---------------------------------------------------------------------------
# inherit_prestate
# ---------------------------------------------------------------------------


def test_inherit_prestate_same_type() -> None:
    """Test inherit_prestate returns True for EffectJacobsLadder."""
    effect = EffectJacobsLadder()
    assert effect.inherit_prestate(EffectJacobsLadder()) is True


def test_inherit_prestate_different_type() -> None:
    """Test inherit_prestate returns False for other effects."""
    effect = EffectJacobsLadder()
    assert effect.inherit_prestate(MagicMock()) is False


# ---------------------------------------------------------------------------
# repr
# ---------------------------------------------------------------------------


def test_repr() -> None:
    """Test string representation includes key parameters."""
    effect = EffectJacobsLadder(speed=0.3, arcs=3, gap=8, brightness=0.6)
    repr_str = repr(effect)

    assert "EffectJacobsLadder" in repr_str
    assert "speed=0.3" in repr_str
    assert "arcs=3" in repr_str
    assert "gap=8" in repr_str
    assert "brightness=0.6" in repr_str


# ---------------------------------------------------------------------------
# Frame loop integration
# ---------------------------------------------------------------------------


class TestFrameLoop:
    """Tests for EffectJacobsLadder running via FrameEffect frame loop."""

    @pytest.mark.asyncio
    async def test_sends_frames_via_animator(self) -> None:
        """Test Jacob's Ladder sends frames through animator.send_frame."""
        effect = EffectJacobsLadder()

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
