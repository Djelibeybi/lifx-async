"""Tests for EffectSonar (radar pulses)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.effects.base import LIFXEffect
from lifx.effects.frame_effect import FrameContext, FrameEffect
from lifx.effects.sonar import EffectSonar, _Obstacle, _Wavefront

# ---------------------------------------------------------------------------
# Default / custom parameters
# ---------------------------------------------------------------------------


def test_sonar_default_parameters() -> None:
    """Test EffectSonar with default parameters."""
    effect = EffectSonar()

    assert effect.name == "sonar"
    assert effect.speed == 8.0
    assert effect.decay == 2.0
    assert effect.pulse_interval == 2.0
    assert effect.obstacle_speed == 0.5
    assert effect.obstacle_hue == 15
    assert effect.obstacle_brightness == 0.8
    assert effect.brightness == 1.0
    assert effect.kelvin == 6500
    assert effect.zones_per_bulb == 1
    assert effect.power_on is True
    assert effect.fps == 20.0
    assert effect.duration is None


def test_sonar_custom_parameters() -> None:
    """Test EffectSonar with custom parameters."""
    effect = EffectSonar(
        speed=4.0,
        decay=1.0,
        pulse_interval=3.0,
        obstacle_speed=1.0,
        obstacle_hue=120,
        obstacle_brightness=0.5,
        brightness=0.6,
        kelvin=5000,
        zones_per_bulb=3,
        power_on=False,
    )

    assert effect.speed == 4.0
    assert effect.decay == 1.0
    assert effect.pulse_interval == 3.0
    assert effect.obstacle_speed == 1.0
    assert effect.obstacle_hue == 120
    assert effect.obstacle_brightness == 0.5
    assert effect.brightness == 0.6
    assert effect.kelvin == 5000
    assert effect.zones_per_bulb == 3
    assert effect.power_on is False


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------


def test_sonar_invalid_speed() -> None:
    """Test EffectSonar with invalid speed raises ValueError."""
    with pytest.raises(ValueError, match="Speed must be"):
        EffectSonar(speed=0)

    with pytest.raises(ValueError, match="Speed must be"):
        EffectSonar(speed=-1.0)


def test_sonar_invalid_decay() -> None:
    """Test EffectSonar with invalid decay raises ValueError."""
    with pytest.raises(ValueError, match="Decay must be"):
        EffectSonar(decay=0)

    with pytest.raises(ValueError, match="Decay must be"):
        EffectSonar(decay=-1.0)


def test_sonar_invalid_pulse_interval() -> None:
    """Test EffectSonar with invalid pulse_interval raises ValueError."""
    with pytest.raises(ValueError, match="Pulse interval must be"):
        EffectSonar(pulse_interval=0)

    with pytest.raises(ValueError, match="Pulse interval must be"):
        EffectSonar(pulse_interval=-1.0)


def test_sonar_invalid_obstacle_speed() -> None:
    """Test EffectSonar with invalid obstacle_speed raises ValueError."""
    with pytest.raises(ValueError, match="Obstacle speed must be"):
        EffectSonar(obstacle_speed=-0.1)


def test_sonar_invalid_obstacle_hue() -> None:
    """Test EffectSonar with invalid obstacle_hue raises ValueError."""
    with pytest.raises(ValueError, match="Obstacle hue must be"):
        EffectSonar(obstacle_hue=-1)

    with pytest.raises(ValueError, match="Obstacle hue must be"):
        EffectSonar(obstacle_hue=361)


def test_sonar_invalid_obstacle_brightness() -> None:
    """Test EffectSonar with invalid obstacle_brightness raises ValueError."""
    with pytest.raises(ValueError, match="Obstacle brightness must be"):
        EffectSonar(obstacle_brightness=1.5)

    with pytest.raises(ValueError, match="Obstacle brightness must be"):
        EffectSonar(obstacle_brightness=-0.1)


def test_sonar_invalid_brightness() -> None:
    """Test EffectSonar with invalid brightness raises ValueError."""
    with pytest.raises(ValueError, match="Brightness must be"):
        EffectSonar(brightness=1.5)

    with pytest.raises(ValueError, match="Brightness must be"):
        EffectSonar(brightness=-0.1)


def test_sonar_invalid_kelvin() -> None:
    """Test EffectSonar with invalid kelvin raises ValueError."""
    with pytest.raises(ValueError, match="Kelvin must be"):
        EffectSonar(kelvin=1000)

    with pytest.raises(ValueError, match="Kelvin must be"):
        EffectSonar(kelvin=10000)


def test_sonar_invalid_zones_per_bulb() -> None:
    """Test EffectSonar with invalid zones_per_bulb raises ValueError."""
    with pytest.raises(ValueError, match="zones_per_bulb must be"):
        EffectSonar(zones_per_bulb=0)

    with pytest.raises(ValueError, match="zones_per_bulb must be"):
        EffectSonar(zones_per_bulb=-1)


def test_sonar_obstacle_speed_zero_is_valid() -> None:
    """Test that obstacle_speed=0 is valid (stationary obstacles)."""
    effect = EffectSonar(obstacle_speed=0.0)
    assert effect.obstacle_speed == 0.0


# ---------------------------------------------------------------------------
# Inheritance tests
# ---------------------------------------------------------------------------


class TestSonarInheritance:
    """Tests for EffectSonar class hierarchy."""

    def test_is_frame_effect(self) -> None:
        """Test EffectSonar extends FrameEffect."""
        effect = EffectSonar()
        assert isinstance(effect, FrameEffect)

    def test_is_lifx_effect(self) -> None:
        """Test EffectSonar extends LIFXEffect."""
        effect = EffectSonar()
        assert isinstance(effect, LIFXEffect)


# ---------------------------------------------------------------------------
# Frame generation tests
# ---------------------------------------------------------------------------


class TestSonarGenerateFrame:
    """Tests for EffectSonar.generate_frame()."""

    def _make_ctx(self, elapsed_s: float = 0.0, pixel_count: int = 16) -> FrameContext:
        """Create a FrameContext for testing."""
        return FrameContext(
            elapsed_s=elapsed_s,
            device_index=0,
            pixel_count=pixel_count,
            canvas_width=pixel_count,
            canvas_height=1,
        )

    def test_returns_correct_pixel_count(self) -> None:
        """Test frame has correct number of pixels."""
        effect = EffectSonar()
        colors = effect.generate_frame(self._make_ctx(pixel_count=24))
        assert len(colors) == 24

    @pytest.mark.parametrize("pixel_count", [1, 8, 16, 48, 82])
    def test_various_pixel_counts(self, pixel_count: int) -> None:
        """Test correct number of colors for various pixel counts."""
        effect = EffectSonar()
        colors = effect.generate_frame(self._make_ctx(pixel_count=pixel_count))
        assert len(colors) == pixel_count

    def test_brightness_in_valid_range(self) -> None:
        """Test all brightness values are 0.0-1.0."""
        effect = EffectSonar()
        # Generate several frames to cover various states.
        for t in [0.0, 0.1, 0.5, 1.0, 2.5]:
            colors = effect.generate_frame(self._make_ctx(elapsed_s=t))
            for color in colors:
                assert 0.0 <= color.brightness <= 1.0

    def test_saturation_in_valid_range(self) -> None:
        """Test all saturation values are 0.0-1.0."""
        effect = EffectSonar()
        for t in [0.0, 0.1, 0.5, 1.0]:
            colors = effect.generate_frame(self._make_ctx(elapsed_s=t))
            for color in colors:
                assert 0.0 <= color.saturation <= 1.0

    def test_hue_is_integer(self) -> None:
        """Test all hue values are integers."""
        effect = EffectSonar()
        for t in [0.0, 0.5, 1.0, 2.5]:
            colors = effect.generate_frame(self._make_ctx(elapsed_s=t))
            for color in colors:
                assert isinstance(color.hue, int)

    def test_kelvin_matches_configured(self) -> None:
        """Test kelvin values match configured kelvin."""
        effect = EffectSonar(kelvin=5000)
        colors = effect.generate_frame(self._make_ctx(elapsed_s=1.0))
        for color in colors:
            assert color.kelvin == 5000

    def test_first_frame_at_zero(self) -> None:
        """Test edge case with elapsed_s=0.0."""
        effect = EffectSonar()
        colors = effect.generate_frame(self._make_ctx(elapsed_s=0.0, pixel_count=16))
        assert len(colors) == 16
        for color in colors:
            assert 0.0 <= color.brightness <= 1.0

    def test_lazy_initialization(self) -> None:
        """Test state is lazily initialized on first frame."""
        effect = EffectSonar()
        assert effect._initialized is False
        assert effect._obstacles == []
        assert effect._sources == []

        effect.generate_frame(self._make_ctx(pixel_count=48))
        assert effect._initialized is True
        assert len(effect._obstacles) >= 1
        assert len(effect._sources) >= 2

    def test_obstacles_created(self) -> None:
        """Test obstacles are created during initialization."""
        effect = EffectSonar()
        effect.generate_frame(self._make_ctx(pixel_count=48))
        assert len(effect._obstacles) >= 1

    def test_sources_include_endpoints(self) -> None:
        """Test sources include both endpoints of the strip."""
        effect = EffectSonar()
        effect.generate_frame(self._make_ctx(pixel_count=48))
        # First source at 0, last at bulb_count-1.
        assert effect._sources[0] == 0.0
        assert effect._sources[-1] == 47.0  # 48 zones / 1 zpb - 1

    def test_frame_changes_over_time(self) -> None:
        """Test that frames evolve after pulses are emitted."""
        effect = EffectSonar(pulse_interval=0.5)
        # Run a few frames to let pulses emit and travel.
        ctx_early = self._make_ctx(elapsed_s=0.0, pixel_count=24)
        colors_early = effect.generate_frame(ctx_early)
        # Advance enough for pulses to emit and move.
        for t_step in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]:
            effect.generate_frame(self._make_ctx(elapsed_s=t_step, pixel_count=24))
        ctx_late = self._make_ctx(elapsed_s=1.0, pixel_count=24)
        colors_late = effect.generate_frame(ctx_late)

        # At least some pixels should differ.
        assert colors_early != colors_late

    def test_obstacle_zones_have_obstacle_hue(self) -> None:
        """Test obstacle zones have the configured obstacle hue."""
        effect = EffectSonar(obstacle_hue=200)
        colors = effect.generate_frame(self._make_ctx(elapsed_s=0.0, pixel_count=48))

        obstacle_colors = [c for c in colors if c.hue == 200 and c.saturation == 1.0]
        assert len(obstacle_colors) >= 1

    def test_wavefront_zones_are_white(self) -> None:
        """Test wavefront zones have zero saturation (white)."""
        effect = EffectSonar()
        colors = effect.generate_frame(self._make_ctx(elapsed_s=0.0, pixel_count=48))

        # Non-obstacle zones should have saturation=0 (white wavefront).
        white_zones = [c for c in colors if c.saturation == 0.0]
        assert len(white_zones) > 0

    def test_zones_per_bulb_grouping(self) -> None:
        """Test zones_per_bulb groups zones into logical bulbs."""
        effect = EffectSonar(zones_per_bulb=3)
        colors = effect.generate_frame(self._make_ctx(elapsed_s=0.0, pixel_count=24))
        assert len(colors) == 24


# ---------------------------------------------------------------------------
# Internal state tests
# ---------------------------------------------------------------------------


class TestSonarInternals:
    """Tests for EffectSonar internal state management."""

    def test_obstacle_count_scales_with_strip_length(self) -> None:
        """Test obstacle count scales with bulb count."""
        # Small strip: 1 obstacle.
        effect_small = EffectSonar()
        effect_small._init_state(16)
        assert len(effect_small._obstacles) == 1

        # Larger strip: more obstacles.
        effect_large = EffectSonar()
        effect_large._init_state(72)
        assert len(effect_large._obstacles) == 3

    def test_obstacles_placed_in_middle_region(self) -> None:
        """Test obstacles are placed in the middle 60% of the strip."""
        effect = EffectSonar()
        effect._init_state(48)
        bulb_count = 48  # zpb=1

        for obs in effect._obstacles:
            assert obs.pos >= bulb_count * 0.2
            assert obs.pos <= bulb_count * 0.8

    def test_sources_between_obstacles(self) -> None:
        """Test sources are placed between adjacent obstacles."""
        effect = EffectSonar()
        effect._init_state(72)  # 3 obstacles with zpb=1

        # Should have: left end + 2 between + right end = 4 sources.
        assert len(effect._sources) == 4
        assert effect._sources[0] == 0.0
        assert effect._sources[-1] == 71.0

    def test_wavefront_creation(self) -> None:
        """Test _Wavefront has correct initial attributes."""
        wf = _Wavefront(source=10.0, direction=1, speed=8.0)
        assert wf.pos == 10.0
        assert wf.direction == 1
        assert wf.source == 10.0
        assert wf.speed == 8.0
        assert wf.alive is True
        assert wf.reflected is False
        assert wf.absorbed is False
        assert wf.last_bulb == -1

    def test_obstacle_creation(self) -> None:
        """Test _Obstacle has correct initial attributes."""
        obs = _Obstacle(pos=24.0)
        assert obs.pos == 24.0
        assert obs.drift_dir in (-1, 1)
        assert obs.next_turn == 0.0

    def test_source_has_live_pulse_empty(self) -> None:
        """Test _source_has_live_pulse returns False when no wavefronts."""
        effect = EffectSonar()
        assert effect._source_has_live_pulse(0.0) is False

    def test_source_has_live_pulse_with_active(self) -> None:
        """Test _source_has_live_pulse returns True for active wavefront."""
        effect = EffectSonar()
        wf = _Wavefront(source=0.0, direction=1, speed=8.0)
        effect._wavefronts.append(wf)
        assert effect._source_has_live_pulse(0.0) is True

    def test_source_has_live_pulse_absorbed(self) -> None:
        """Test _source_has_live_pulse returns False for absorbed wavefront."""
        effect = EffectSonar()
        wf = _Wavefront(source=0.0, direction=1, speed=8.0)
        wf.absorbed = True
        effect._wavefronts.append(wf)
        assert effect._source_has_live_pulse(0.0) is False

    def test_source_has_live_pulse_dead(self) -> None:
        """Test _source_has_live_pulse returns False for dead wavefront."""
        effect = EffectSonar()
        wf = _Wavefront(source=0.0, direction=1, speed=8.0)
        wf.alive = False
        effect._wavefronts.append(wf)
        assert effect._source_has_live_pulse(0.0) is False

    def test_decay_bulbs_reduces_brightness(self) -> None:
        """Test _decay_bulbs reduces brightness over time."""
        effect = EffectSonar(decay=1.0)
        effect._bulb_brightness = {0: 1.0, 5: 0.8, 10: 0.1}
        effect._decay_bulbs(0.2)

        # Brightness should decrease (decay_rate = 0.2 / 1.0 = 0.2).
        assert effect._bulb_brightness[0] < 1.0
        assert effect._bulb_brightness[5] < 0.8
        # Bulb 10 should be dead (0.1 - 0.2 < 0).
        assert 10 not in effect._bulb_brightness

    def test_decay_bulbs_removes_dead(self) -> None:
        """Test _decay_bulbs removes completely decayed bulbs."""
        effect = EffectSonar(decay=0.1)
        effect._bulb_brightness = {0: 0.01}
        effect._decay_bulbs(0.5)
        assert 0 not in effect._bulb_brightness

    def test_dt_clamped_on_large_jump(self) -> None:
        """Test that large time jumps are clamped to prevent instability."""
        effect = EffectSonar()
        ctx1 = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        effect.generate_frame(ctx1)

        # Large time jump -- should be clamped internally.
        ctx2 = FrameContext(
            elapsed_s=100.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        # Should not crash.
        colors = effect.generate_frame(ctx2)
        assert len(colors) == 16


# ---------------------------------------------------------------------------
# Obstacle drift tests
# ---------------------------------------------------------------------------


class TestSonarObstacleDrift:
    """Tests for obstacle drift behavior."""

    def test_obstacles_drift_with_speed(self) -> None:
        """Test obstacles move when obstacle_speed > 0."""
        effect = EffectSonar(obstacle_speed=2.0)
        effect._init_state(48)
        original_pos = effect._obstacles[0].pos

        # Force a known drift direction.
        effect._obstacles[0].drift_dir = 1
        effect._obstacles[0].next_turn = 999.0

        effect._drift_obstacles(t=1.0, dt=0.1, bulb_count=48)
        assert effect._obstacles[0].pos != original_pos

    def test_obstacles_respect_edge_gap(self) -> None:
        """Test obstacles don't drift past minimum edge gap."""
        effect = EffectSonar(obstacle_speed=100.0)
        effect._obstacles = [_Obstacle(pos=5.0)]
        effect._obstacles[0].drift_dir = -1
        effect._obstacles[0].next_turn = 999.0

        effect._drift_obstacles(t=1.0, dt=1.0, bulb_count=48)
        # Should be clamped to MIN_GAP_BULBS = 3.
        assert effect._obstacles[0].pos >= 3.0

    def test_obstacles_reverse_at_boundary(self) -> None:
        """Test obstacles reverse direction when hitting boundary."""
        effect = EffectSonar(obstacle_speed=100.0)
        effect._obstacles = [_Obstacle(pos=4.0)]
        effect._obstacles[0].drift_dir = -1
        effect._obstacles[0].next_turn = 999.0

        effect._drift_obstacles(t=1.0, dt=1.0, bulb_count=48)
        # Should reverse to +1 after hitting left boundary.
        assert effect._obstacles[0].drift_dir == 1

    def test_stationary_obstacles_dont_move(self) -> None:
        """Test obstacles don't move when obstacle_speed=0."""
        effect = EffectSonar(obstacle_speed=0.0)
        effect._init_state(48)
        original_pos = effect._obstacles[0].pos

        effect._drift_obstacles(t=1.0, dt=0.1, bulb_count=48)
        assert effect._obstacles[0].pos == original_pos


# ---------------------------------------------------------------------------
# Pulse emission tests
# ---------------------------------------------------------------------------


class TestSonarPulseEmission:
    """Tests for pulse emission behavior."""

    def test_pulses_emitted_on_interval(self) -> None:
        """Test pulses are emitted when interval elapses."""
        effect = EffectSonar(pulse_interval=1.0)
        effect._init_state(48)
        effect._last_pulse_t = -999.0

        effect._emit_pulses(t=0.0, bulb_count=48)
        assert len(effect._wavefronts) > 0

    def test_no_early_emission(self) -> None:
        """Test pulses are not emitted before interval."""
        effect = EffectSonar(pulse_interval=5.0)
        effect._init_state(48)
        effect._last_pulse_t = 0.0

        effect._emit_pulses(t=1.0, bulb_count=48)
        assert len(effect._wavefronts) == 0

    def test_left_source_emits_rightward(self) -> None:
        """Test left endpoint source emits rightward only."""
        effect = EffectSonar(pulse_interval=1.0)
        effect._sources = [0.0]
        effect._last_pulse_t = -999.0

        effect._emit_pulses(t=0.0, bulb_count=48)
        assert len(effect._wavefronts) == 1
        assert effect._wavefronts[0].direction == 1

    def test_right_source_emits_leftward(self) -> None:
        """Test right endpoint source emits leftward only."""
        effect = EffectSonar(pulse_interval=1.0)
        effect._sources = [47.0]
        effect._last_pulse_t = -999.0

        effect._emit_pulses(t=0.0, bulb_count=48)
        assert len(effect._wavefronts) == 1
        assert effect._wavefronts[0].direction == -1

    def test_middle_source_emits_both_ways(self) -> None:
        """Test middle source emits in both directions."""
        effect = EffectSonar(pulse_interval=1.0)
        effect._sources = [24.0]
        effect._last_pulse_t = -999.0

        effect._emit_pulses(t=0.0, bulb_count=48)
        assert len(effect._wavefronts) == 2
        directions = {wf.direction for wf in effect._wavefronts}
        assert directions == {-1, 1}

    def test_no_double_emission_per_source(self) -> None:
        """Test a source with a live pulse does not emit again."""
        effect = EffectSonar(pulse_interval=1.0)
        effect._sources = [0.0]
        effect._last_pulse_t = -999.0

        effect._emit_pulses(t=0.0, bulb_count=48)
        count_after_first = len(effect._wavefronts)

        effect._last_pulse_t = -999.0  # Reset interval.
        effect._emit_pulses(t=2.0, bulb_count=48)
        # Should not add more since source 0.0 already has a live pulse.
        assert len(effect._wavefronts) == count_after_first


# ---------------------------------------------------------------------------
# Wavefront update tests
# ---------------------------------------------------------------------------


class TestSonarWavefrontUpdate:
    """Tests for wavefront movement and reflection."""

    def test_wavefront_moves_forward(self) -> None:
        """Test wavefront position advances over time."""
        effect = EffectSonar(speed=10.0)
        effect._obstacles = []
        wf = _Wavefront(source=0.0, direction=1, speed=10.0)
        effect._wavefronts = [wf]

        effect._update_wavefronts(dt=0.1, bulb_count=48)
        assert wf.pos > 0.0

    def test_wavefront_stamps_bulbs(self) -> None:
        """Test wavefront stamps brightness on bulbs it passes."""
        effect = EffectSonar(speed=10.0)
        effect._obstacles = []
        wf = _Wavefront(source=0.0, direction=1, speed=10.0)
        effect._wavefronts = [wf]

        effect._update_wavefronts(dt=0.1, bulb_count=48)
        # Should have stamped at least one bulb.
        assert len(effect._bulb_brightness) > 0

    def test_wavefront_reflects_off_obstacle(self) -> None:
        """Test wavefront reflects when hitting an obstacle."""
        effect = EffectSonar(speed=100.0)
        obs = _Obstacle(pos=10.0)
        effect._obstacles = [obs]

        wf = _Wavefront(source=0.0, direction=1, speed=100.0)
        effect._wavefronts = [wf]

        # Large dt so wavefront overshoots obstacle.
        effect._update_wavefronts(dt=0.5, bulb_count=48)

        assert wf.reflected is True
        assert wf.direction == -1

    def test_wavefront_absorbed_after_reflection(self) -> None:
        """Test wavefront is absorbed when returning to source."""
        effect = EffectSonar(speed=100.0)
        obs = _Obstacle(pos=10.0)
        effect._obstacles = [obs]

        wf = _Wavefront(source=0.0, direction=1, speed=100.0)
        effect._wavefronts = [wf]

        # First: reflect off obstacle.
        effect._update_wavefronts(dt=0.15, bulb_count=48)
        assert wf.reflected is True

        # Then: return to source.
        effect._update_wavefronts(dt=0.15, bulb_count=48)
        # Wavefront should be absorbed or removed.
        absorbed_or_dead = wf.absorbed or not wf.alive
        assert absorbed_or_dead

    def test_wavefront_killed_off_string(self) -> None:
        """Test wavefront dies if it goes far off the string."""
        effect = EffectSonar(speed=100.0)
        effect._obstacles = []

        wf = _Wavefront(source=0.0, direction=-1, speed=100.0)
        effect._wavefronts = [wf]

        effect._update_wavefronts(dt=1.0, bulb_count=48)
        # Wavefront should be pruned (off-string).
        assert len(effect._wavefronts) == 0

    def test_dead_wavefronts_pruned(self) -> None:
        """Test dead wavefronts are removed from the list."""
        effect = EffectSonar()
        effect._obstacles = []

        wf = _Wavefront(source=0.0, direction=1, speed=1.0)
        wf.alive = False
        effect._wavefronts = [wf]

        effect._update_wavefronts(dt=0.1, bulb_count=48)
        assert len(effect._wavefronts) == 0


# ---------------------------------------------------------------------------
# Frame loop tests
# ---------------------------------------------------------------------------


class TestSonarFrameLoop:
    """Tests for EffectSonar running via FrameEffect frame loop."""

    @pytest.mark.asyncio
    async def test_sends_frames_via_animator(self) -> None:
        """Test sonar sends frames through animator.send_frame."""
        effect = EffectSonar()

        animator = MagicMock()
        animator.pixel_count = 24
        animator.canvas_width = 24
        animator.canvas_height = 1
        animator.send_frame = MagicMock()
        effect._animators = [animator]

        play_task = asyncio.create_task(effect.async_play())
        await asyncio.sleep(0.1)
        effect.stop()
        await asyncio.wait_for(play_task, timeout=1.0)

        assert animator.send_frame.call_count > 0


# ---------------------------------------------------------------------------
# Effect protocol tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sonar_from_poweroff() -> None:
    """Test from_poweroff_hsbk returns dim white."""
    effect = EffectSonar(kelvin=5000)
    light = MagicMock()
    result = await effect.from_poweroff_hsbk(light)

    assert result.hue == 0
    assert result.saturation == 0.0
    assert result.brightness == 0.0
    assert result.kelvin == 5000


@pytest.mark.asyncio
async def test_sonar_is_light_compatible_with_multizone() -> None:
    """Test is_light_compatible returns True for multizone lights."""
    effect = EffectSonar()
    light = MagicMock()
    capabilities = MagicMock()
    capabilities.has_multizone = True
    light.capabilities = capabilities

    assert await effect.is_light_compatible(light) is True


@pytest.mark.asyncio
async def test_sonar_is_light_compatible_without_multizone() -> None:
    """Test is_light_compatible returns False for non-multizone lights."""
    effect = EffectSonar()
    light = MagicMock()
    capabilities = MagicMock()
    capabilities.has_multizone = False
    light.capabilities = capabilities

    assert await effect.is_light_compatible(light) is False


@pytest.mark.asyncio
async def test_sonar_is_light_compatible_none_capabilities() -> None:
    """Test is_light_compatible loads capabilities when None."""
    effect = EffectSonar()
    light = MagicMock()
    light.capabilities = None

    async def ensure_caps() -> None:
        caps = MagicMock()
        caps.has_multizone = True
        light.capabilities = caps

    light._ensure_capabilities = AsyncMock(side_effect=ensure_caps)

    assert await effect.is_light_compatible(light) is True
    light._ensure_capabilities.assert_called_once()


def test_sonar_inherit_prestate() -> None:
    """Test inherit_prestate returns True for EffectSonar."""
    effect = EffectSonar()
    assert effect.inherit_prestate(EffectSonar()) is True
    assert effect.inherit_prestate(MagicMock()) is False


def test_sonar_repr() -> None:
    """Test EffectSonar string representation."""
    effect = EffectSonar(speed=4.0, decay=1.0, obstacle_hue=120, brightness=0.6)
    repr_str = repr(effect)

    assert "EffectSonar" in repr_str
    assert "speed=4.0" in repr_str
    assert "decay=1.0" in repr_str
    assert "obstacle_hue=120" in repr_str
    assert "brightness=0.6" in repr_str
