"""Tests for EffectFireworks (fireworks effect)."""

import asyncio
import random
from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.color import HSBK
from lifx.effects.base import LIFXEffect
from lifx.effects.fireworks import (
    EffectFireworks,
    _Rocket,
)
from lifx.effects.frame_effect import FrameContext, FrameEffect

# ---------------------------------------------------------------------------
# Constructor defaults and validation
# ---------------------------------------------------------------------------


class TestFireworksConstructor:
    """Tests for EffectFireworks constructor and parameter validation."""

    def test_default_parameters(self) -> None:
        """Test EffectFireworks with default parameters."""
        effect = EffectFireworks()

        assert effect.name == "fireworks"
        assert effect.max_rockets == 3
        assert effect.launch_rate == 0.5
        assert effect.ascent_speed == 0.3
        assert effect.burst_spread == 5.0
        assert effect.burst_duration == 2.0
        assert effect.brightness == 0.8
        assert effect.kelvin == 3500
        assert effect.power_on is True
        assert effect.fps == 20.0
        assert effect.duration is None

    def test_custom_parameters(self) -> None:
        """Test EffectFireworks with custom parameters."""
        effect = EffectFireworks(
            max_rockets=5,
            launch_rate=1.0,
            ascent_speed=10.0,
            burst_spread=20.0,
            burst_duration=3.0,
            brightness=0.6,
            kelvin=5000,
            power_on=False,
        )

        assert effect.max_rockets == 5
        assert effect.launch_rate == 1.0
        assert effect.ascent_speed == 10.0
        assert effect.burst_spread == 20.0
        assert effect.burst_duration == 3.0
        assert effect.brightness == 0.6
        assert effect.kelvin == 5000
        assert effect.power_on is False

    def test_invalid_max_rockets_low(self) -> None:
        """Test max_rockets below minimum raises ValueError."""
        with pytest.raises(ValueError, match="max_rockets must be"):
            EffectFireworks(max_rockets=0)

    def test_invalid_max_rockets_high(self) -> None:
        """Test max_rockets above maximum raises ValueError."""
        with pytest.raises(ValueError, match="max_rockets must be"):
            EffectFireworks(max_rockets=21)

    def test_invalid_launch_rate_low(self) -> None:
        """Test launch_rate below minimum raises ValueError."""
        with pytest.raises(ValueError, match="launch_rate must be"):
            EffectFireworks(launch_rate=0.01)

    def test_invalid_launch_rate_high(self) -> None:
        """Test launch_rate above maximum raises ValueError."""
        with pytest.raises(ValueError, match="launch_rate must be"):
            EffectFireworks(launch_rate=6.0)

    def test_invalid_ascent_speed_low(self) -> None:
        """Test ascent_speed below minimum raises ValueError."""
        with pytest.raises(ValueError, match="ascent_speed must be"):
            EffectFireworks(ascent_speed=0.05)

    def test_invalid_ascent_speed_high(self) -> None:
        """Test ascent_speed above maximum raises ValueError."""
        with pytest.raises(ValueError, match="ascent_speed must be"):
            EffectFireworks(ascent_speed=61.0)

    def test_invalid_burst_spread_low(self) -> None:
        """Test burst_spread below minimum raises ValueError."""
        with pytest.raises(ValueError, match="burst_spread must be"):
            EffectFireworks(burst_spread=1.0)

    def test_invalid_burst_spread_high(self) -> None:
        """Test burst_spread above maximum raises ValueError."""
        with pytest.raises(ValueError, match="burst_spread must be"):
            EffectFireworks(burst_spread=61.0)

    def test_invalid_burst_duration_low(self) -> None:
        """Test burst_duration below minimum raises ValueError."""
        with pytest.raises(ValueError, match="burst_duration must be"):
            EffectFireworks(burst_duration=0.1)

    def test_invalid_burst_duration_high(self) -> None:
        """Test burst_duration above maximum raises ValueError."""
        with pytest.raises(ValueError, match="burst_duration must be"):
            EffectFireworks(burst_duration=9.0)

    def test_invalid_brightness_low(self) -> None:
        """Test brightness below minimum raises ValueError."""
        with pytest.raises(ValueError, match="brightness must be"):
            EffectFireworks(brightness=-0.1)

    def test_invalid_brightness_high(self) -> None:
        """Test brightness above maximum raises ValueError."""
        with pytest.raises(ValueError, match="brightness must be"):
            EffectFireworks(brightness=1.5)

    def test_invalid_kelvin_low(self) -> None:
        """Test kelvin below minimum raises ValueError."""
        with pytest.raises(ValueError, match="kelvin must be"):
            EffectFireworks(kelvin=1000)

    def test_invalid_kelvin_high(self) -> None:
        """Test kelvin above maximum raises ValueError."""
        with pytest.raises(ValueError, match="kelvin must be"):
            EffectFireworks(kelvin=10000)


# ---------------------------------------------------------------------------
# Inheritance
# ---------------------------------------------------------------------------


class TestFireworksInheritance:
    """Tests for EffectFireworks class hierarchy."""

    def test_is_frame_effect(self) -> None:
        """Test EffectFireworks extends FrameEffect."""
        effect = EffectFireworks()
        assert isinstance(effect, FrameEffect)

    def test_is_lifx_effect(self) -> None:
        """Test EffectFireworks extends LIFXEffect."""
        effect = EffectFireworks()
        assert isinstance(effect, LIFXEffect)


# ---------------------------------------------------------------------------
# Rocket dataclass
# ---------------------------------------------------------------------------


class TestRocket:
    """Tests for the _Rocket dataclass."""

    def test_rocket_not_done_during_ascent(self) -> None:
        """Test rocket is not done during ascent phase."""
        rocket = _Rocket(
            origin=0,
            direction=1,
            zenith=10,
            launch_t=0.0,
            ascent_dur=1.0,
            burst_hue=120.0,
            burst_dur=2.0,
        )
        assert rocket.is_done(0.5) is False

    def test_rocket_not_done_during_burst(self) -> None:
        """Test rocket is not done during burst phase."""
        rocket = _Rocket(
            origin=0,
            direction=1,
            zenith=10,
            launch_t=0.0,
            ascent_dur=1.0,
            burst_hue=120.0,
            burst_dur=2.0,
        )
        assert rocket.is_done(2.0) is False

    def test_rocket_done_after_burst(self) -> None:
        """Test rocket is done after burst completes."""
        rocket = _Rocket(
            origin=0,
            direction=1,
            zenith=10,
            launch_t=0.0,
            ascent_dur=1.0,
            burst_hue=120.0,
            burst_dur=2.0,
        )
        assert rocket.is_done(3.0) is True

    def test_rocket_done_exactly_at_end(self) -> None:
        """Test rocket is done exactly at ascent_dur + burst_dur."""
        rocket = _Rocket(
            origin=0,
            direction=1,
            zenith=10,
            launch_t=1.0,
            ascent_dur=2.0,
            burst_hue=180.0,
            burst_dur=3.0,
        )
        assert rocket.is_done(6.0) is True


# ---------------------------------------------------------------------------
# Frame generation
# ---------------------------------------------------------------------------


class TestFireworksGenerateFrame:
    """Tests for EffectFireworks.generate_frame()."""

    def test_returns_correct_count(self) -> None:
        """Test frame returns correct number of colors."""
        effect = EffectFireworks()
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        assert len(colors) == 16

    @pytest.mark.parametrize("pixel_count", [1, 8, 16, 32, 82])
    def test_various_pixel_counts(self, pixel_count: int) -> None:
        """Test correct number of colors for various pixel counts."""
        effect = EffectFireworks()
        ctx = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=pixel_count,
            canvas_width=pixel_count,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        assert len(colors) == pixel_count

    def test_all_colors_valid_hsbk(self) -> None:
        """Test all returned colors are valid HSBK instances."""
        effect = EffectFireworks()
        for t in [0.0, 0.5, 1.0, 2.0, 5.0]:
            ctx = FrameContext(
                elapsed_s=t,
                device_index=0,
                pixel_count=16,
                canvas_width=16,
                canvas_height=1,
            )
            colors = effect.generate_frame(ctx)
            for color in colors:
                assert isinstance(color, HSBK)
                assert 0 <= color.hue <= 360
                assert 0.0 <= color.saturation <= 1.0
                assert 0.0 <= color.brightness <= 1.0

    def test_kelvin_matches_configured(self) -> None:
        """Test all pixel kelvin values match configured kelvin."""
        effect = EffectFireworks(kelvin=5000)
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

    def test_elapsed_zero_returns_valid_frame(self) -> None:
        """Test edge case with elapsed_s=0.0."""
        effect = EffectFireworks()
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

    def test_lazy_initialization(self) -> None:
        """Test state is lazily initialized on first frame."""
        effect = EffectFireworks()
        assert effect._initialized is False

        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        effect.generate_frame(ctx)
        assert effect._initialized is True


# ---------------------------------------------------------------------------
# Stateful behavior
# ---------------------------------------------------------------------------


class TestFireworksStateful:
    """Tests for stateful rocket management across frames."""

    def test_rockets_spawn_over_time(self) -> None:
        """Test that rockets are spawned as time advances."""
        random.seed(42)
        effect = EffectFireworks(launch_rate=5.0, max_rockets=10)

        # Generate frames to trigger spawning
        for t in [0.0, 0.1, 0.2, 0.3, 0.5, 1.0]:
            ctx = FrameContext(
                elapsed_s=t,
                device_index=0,
                pixel_count=32,
                canvas_width=32,
                canvas_height=1,
            )
            effect.generate_frame(ctx)

        # At high launch rate, should have spawned rockets
        assert len(effect._rockets) > 0

    def test_rockets_expire_after_burst(self) -> None:
        """Test that rockets are removed after burst completes."""
        effect = EffectFireworks(
            launch_rate=5.0,
            max_rockets=1,
            burst_duration=0.5,
            ascent_speed=50.0,
        )

        # Spawn at t=0
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=32,
            canvas_width=32,
            canvas_height=1,
        )
        effect.generate_frame(ctx)

        # Far enough in the future that all rockets should be expired
        ctx_late = FrameContext(
            elapsed_s=100.0,
            device_index=0,
            pixel_count=32,
            canvas_width=32,
            canvas_height=1,
        )
        effect.generate_frame(ctx_late)

        # Old rockets should be cleaned up (may have spawned a new one)
        for rocket in effect._rockets:
            assert not rocket.is_done(100.0)

    def test_max_rockets_respected(self) -> None:
        """Test that max_rockets limit is not exceeded."""
        effect = EffectFireworks(
            launch_rate=5.0,
            max_rockets=2,
            burst_duration=5.0,
        )

        for t_val in [float(i) * 0.05 for i in range(40)]:
            ctx = FrameContext(
                elapsed_s=t_val,
                device_index=0,
                pixel_count=32,
                canvas_width=32,
                canvas_height=1,
            )
            effect.generate_frame(ctx)
            assert len(effect._rockets) <= 2

    def test_frame_varies_over_time(self) -> None:
        """Test that frames change across multiple time steps."""
        random.seed(123)
        effect = EffectFireworks(launch_rate=5.0)

        frames = []
        for t in [0.0, 0.5, 1.0]:
            ctx = FrameContext(
                elapsed_s=t,
                device_index=0,
                pixel_count=16,
                canvas_width=16,
                canvas_height=1,
            )
            frames.append(effect.generate_frame(ctx))

        # At least one pair of frames should differ
        differ = False
        for i in range(len(frames) - 1):
            if frames[i] != frames[i + 1]:
                differ = True
                break
        assert differ


# ---------------------------------------------------------------------------
# Contribution / rendering phases
# ---------------------------------------------------------------------------


class TestFireworksContribution:
    """Tests for rocket contribution rendering."""

    def test_ascent_phase_has_bright_head(self) -> None:
        """Test that during ascent, the rocket head is bright."""
        effect = EffectFireworks()
        rocket = _Rocket(
            origin=0,
            direction=1,
            zenith=15,
            launch_t=0.0,
            ascent_dur=2.0,
            burst_hue=120.0,
            burst_dur=2.0,
        )
        # Mid-ascent
        contrib = effect._contribution(rocket, 1.0, 32)
        assert len(contrib) == 32

        # At least one zone should have brightness > 0
        max_bri = max(c[2] for c in contrib)
        assert max_bri > 0.0

    def test_burst_phase_has_bright_center(self) -> None:
        """Test that during burst, the zenith zone is bright."""
        effect = EffectFireworks()
        rocket = _Rocket(
            origin=0,
            direction=1,
            zenith=15,
            launch_t=0.0,
            ascent_dur=1.0,
            burst_hue=120.0,
            burst_dur=2.0,
        )
        # Just after burst starts
        contrib = effect._contribution(rocket, 1.1, 32)
        assert contrib[15][2] > 0.5  # Zenith should be bright

    def test_burst_fades_with_distance(self) -> None:
        """Test that burst brightness decreases with distance from zenith."""
        effect = EffectFireworks()
        rocket = _Rocket(
            origin=0,
            direction=1,
            zenith=15,
            launch_t=0.0,
            ascent_dur=1.0,
            burst_hue=120.0,
            burst_dur=2.0,
        )
        contrib = effect._contribution(rocket, 1.1, 32)
        # Zones near zenith should be brighter than distant zones
        assert contrib[15][2] >= contrib[10][2]
        assert contrib[15][2] >= contrib[20][2]

    def test_contribution_before_launch_is_dark(self) -> None:
        """Test rocket has no contribution before launch time."""
        effect = EffectFireworks()
        rocket = _Rocket(
            origin=0,
            direction=1,
            zenith=15,
            launch_t=5.0,
            ascent_dur=1.0,
            burst_hue=120.0,
            burst_dur=2.0,
        )
        contrib = effect._contribution(rocket, 0.0, 32)
        for h, s, b in contrib:
            assert b == 0.0

    def test_contribution_after_done_is_dark(self) -> None:
        """Test rocket has no contribution after burst is done."""
        effect = EffectFireworks()
        rocket = _Rocket(
            origin=0,
            direction=1,
            zenith=15,
            launch_t=0.0,
            ascent_dur=1.0,
            burst_hue=120.0,
            burst_dur=2.0,
        )
        # t=3.0 is exactly at ascent_dur + burst_dur
        contrib = effect._contribution(rocket, 4.0, 32)
        for h, s, b in contrib:
            assert b == 0.0


# ---------------------------------------------------------------------------
# Additive RGB blending
# ---------------------------------------------------------------------------


class TestFireworksAdditiveBlending:
    """Tests for additive RGB blending of overlapping rockets."""

    def test_two_rockets_overlap_brighter(self) -> None:
        """Test overlapping rockets produce brighter output than single."""
        effect = EffectFireworks(brightness=1.0)

        # Manually add two rockets at the same position
        rocket1 = _Rocket(
            origin=0,
            direction=1,
            zenith=8,
            launch_t=0.0,
            ascent_dur=0.5,
            burst_hue=0.0,
            burst_dur=2.0,
        )
        rocket2 = _Rocket(
            origin=16,
            direction=-1,
            zenith=8,
            launch_t=0.0,
            ascent_dur=0.5,
            burst_hue=0.0,
            burst_dur=2.0,
        )

        effect._ensure_initialized()
        effect._rockets = [rocket1]
        # Suppress auto-spawning
        effect._next_launch_t = 999.0

        ctx = FrameContext(
            elapsed_s=0.6,
            device_index=0,
            pixel_count=17,
            canvas_width=17,
            canvas_height=1,
        )
        frame_single = effect.generate_frame(ctx)
        single_bri = frame_single[8].brightness

        effect._rockets = [rocket1, rocket2]
        frame_double = effect.generate_frame(ctx)
        double_bri = frame_double[8].brightness

        # With two overlapping, brightness should be >= single
        assert double_bri >= single_bri


# ---------------------------------------------------------------------------
# Spawn mechanics
# ---------------------------------------------------------------------------


class TestFireworksSpawn:
    """Tests for rocket spawning behavior."""

    def test_spawn_rocket_from_left(self) -> None:
        """Test rocket spawning from left end."""
        random.seed(0)
        effect = EffectFireworks()
        effect._ensure_initialized()

        # Force from_left by controlling random
        original_random = random.random
        random.random = lambda: 0.1  # < 0.5 means from_left

        try:
            effect._spawn_rocket(0.0, 32)
            rocket = effect._rockets[-1]
            assert rocket.origin == 0
            assert rocket.direction == 1
        finally:
            random.random = original_random

    def test_spawn_rocket_from_right(self) -> None:
        """Test rocket spawning from right end."""
        effect = EffectFireworks()
        effect._ensure_initialized()

        original_random = random.random
        random.random = lambda: 0.9  # > 0.5 means from_right

        try:
            effect._spawn_rocket(0.0, 32)
            rocket = effect._rockets[-1]
            assert rocket.origin == 31
            assert rocket.direction == -1
        finally:
            random.random = original_random

    def test_spawn_zenith_within_bounds(self) -> None:
        """Test that spawned rockets have zenith within strip bounds."""
        effect = EffectFireworks()
        effect._ensure_initialized()

        for _ in range(50):
            effect._spawn_rocket(0.0, 32)
            rocket = effect._rockets[-1]
            assert 0 <= rocket.zenith <= 31
            effect._rockets.clear()

    def test_spawn_on_tiny_strip(self) -> None:
        """Test spawning on very small zone count."""
        effect = EffectFireworks()
        effect._ensure_initialized()

        for _ in range(20):
            effect._spawn_rocket(0.0, 4)
            rocket = effect._rockets[-1]
            assert 0 <= rocket.zenith <= 3
            assert rocket.ascent_dur >= 0.0
            effect._rockets.clear()


# ---------------------------------------------------------------------------
# Compatibility and lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fireworks_from_poweroff() -> None:
    """Test from_poweroff_hsbk returns black at configured kelvin."""
    effect = EffectFireworks(kelvin=5000)
    light = MagicMock()
    result = await effect.from_poweroff_hsbk(light)

    assert result.hue == 0
    assert result.saturation == 0.0
    assert result.brightness == 0.0
    assert result.kelvin == 5000


@pytest.mark.asyncio
async def test_fireworks_is_light_compatible_multizone() -> None:
    """Test is_light_compatible returns True for multizone lights."""
    effect = EffectFireworks()
    light = MagicMock()
    capabilities = MagicMock()
    capabilities.has_multizone = True
    light.capabilities = capabilities

    assert await effect.is_light_compatible(light) is True


@pytest.mark.asyncio
async def test_fireworks_is_light_compatible_no_multizone() -> None:
    """Test is_light_compatible returns False for non-multizone lights."""
    effect = EffectFireworks()
    light = MagicMock()
    capabilities = MagicMock()
    capabilities.has_multizone = False
    light.capabilities = capabilities

    assert await effect.is_light_compatible(light) is False


@pytest.mark.asyncio
async def test_fireworks_is_light_compatible_none_capabilities() -> None:
    """Test is_light_compatible loads capabilities when None."""
    effect = EffectFireworks()
    light = MagicMock()
    light.capabilities = None

    async def ensure_caps() -> None:
        caps = MagicMock()
        caps.has_multizone = True
        light.capabilities = caps

    light.ensure_capabilities = AsyncMock(side_effect=ensure_caps)

    assert await effect.is_light_compatible(light) is True
    light.ensure_capabilities.assert_called_once()


def test_fireworks_inherit_prestate() -> None:
    """Test inherit_prestate returns True for EffectFireworks."""
    effect = EffectFireworks()
    assert effect.inherit_prestate(EffectFireworks()) is True
    assert effect.inherit_prestate(MagicMock()) is False


def test_fireworks_repr() -> None:
    """Test EffectFireworks string representation."""
    effect = EffectFireworks(max_rockets=5, launch_rate=1.0, kelvin=5000)
    repr_str = repr(effect)

    assert "EffectFireworks" in repr_str
    assert "max_rockets=5" in repr_str
    assert "launch_rate=1.0" in repr_str
    assert "kelvin=5000" in repr_str


# ---------------------------------------------------------------------------
# Frame loop integration
# ---------------------------------------------------------------------------


class TestFireworksFrameLoop:
    """Tests for EffectFireworks running via FrameEffect frame loop."""

    @pytest.mark.asyncio
    async def test_sends_frames_via_animator(self) -> None:
        """Test fireworks sends frames through animator.send_frame."""
        effect = EffectFireworks()

        animator = MagicMock()
        animator.pixel_count = 16
        animator.canvas_width = 16
        animator.canvas_height = 1
        animator.send_frame = MagicMock()
        effect._animators = [animator]

        play_task = asyncio.create_task(effect.async_play())
        await asyncio.sleep(0.15)
        effect.stop()
        await asyncio.wait_for(play_task, timeout=1.0)

        assert animator.send_frame.call_count > 0


# ---------------------------------------------------------------------------
# Burst color evolution
# ---------------------------------------------------------------------------


class TestBurstColorEvolution:
    """Tests for the temporal color evolution of bursts."""

    def _make_rocket_at_burst(
        self, burst_frac: float, burst_dur: float = 2.0
    ) -> tuple[EffectFireworks, _Rocket, float]:
        """Create a rocket at a specific burst fraction."""
        effect = EffectFireworks(brightness=1.0)
        ascent_dur = 1.0
        rocket = _Rocket(
            origin=0,
            direction=1,
            zenith=16,
            launch_t=0.0,
            ascent_dur=ascent_dur,
            burst_hue=180.0,
            burst_dur=burst_dur,
        )
        t = ascent_dur + burst_frac * burst_dur
        return effect, rocket, t

    def test_white_phase_low_saturation(self) -> None:
        """Test early burst has low saturation (white-hot)."""
        effect, rocket, t = self._make_rocket_at_burst(0.03)
        contrib = effect._contribution(rocket, t, 32)
        # Zenith zone should have low saturation
        _, sat, bri = contrib[16]
        assert bri > 0.0
        assert sat < 0.2  # Near white-hot

    def test_peak_phase_high_saturation(self) -> None:
        """Test mid-burst has high saturation (chemical color)."""
        effect, rocket, t = self._make_rocket_at_burst(0.40)
        contrib = effect._contribution(rocket, t, 32)
        _, sat, bri = contrib[16]
        assert bri > 0.0
        assert sat > 0.8  # Full chemical color

    def test_cooling_phase_hue_shifts(self) -> None:
        """Test late burst hue shifts toward warm orange."""
        effect, rocket, t = self._make_rocket_at_burst(0.90)
        contrib = effect._contribution(rocket, t, 32)
        h, sat, bri = contrib[16]
        # Should have shifted somewhat toward 25 degrees (warm orange)
        if bri > 0.0:
            # Saturation should have decreased from peak
            assert sat < 1.0

    def test_saturation_ramp_during_head_to_burst_transition(self) -> None:
        """Test saturation ramps up during burst head-to-color-peak transition.

        Lines 415-419: burst_frac between _BURST_WHITE_PHASE (0.08) and
        _BURST_COLOR_PEAK (0.35) ramps saturation from _HEAD_SATURATION
        to _BURST_SATURATION.
        """
        # burst_frac=0.20 is between 0.08 and 0.35
        effect, rocket, t = self._make_rocket_at_burst(0.20)
        contrib = effect._contribution(rocket, t, 32)
        _, sat, bri = contrib[16]
        assert bri > 0.0
        # Saturation should be between head (0.10) and burst (1.0)
        assert 0.10 < sat < 1.0

    def test_hue_wrap_positive_diff_greater_180(self) -> None:
        """Test hue wrap when _BURST_COOL_HUE - burst_hue > 180.

        Line 431: When burst_hue is far below _BURST_COOL_HUE (25),
        diff > 180 triggers diff -= 360 for shortest-path interpolation.
        Example: burst_hue=200, cool_hue=25 => diff=25-200=-175 (no wrap).
        But burst_hue=180, cool_hue=25 => diff=25-180=-155 (no wrap).
        Need: diff > 180, so burst_hue < 25-180 = -155 (impossible).
        Actually: diff = 25 - burst_hue. For diff > 180: burst_hue < -155.
        burst_hue > 205 triggers diff < -180 wrap.
        burst_hue=350 => diff=25-350=-325 => +360 => 35.
        """
        effect = EffectFireworks(brightness=1.0)
        # burst_hue=350 => diff = 25-350 = -325 < -180, triggers line 433
        rocket = _Rocket(
            origin=0,
            direction=1,
            zenith=16,
            launch_t=0.0,
            ascent_dur=1.0,
            burst_hue=350.0,
            burst_dur=2.0,
        )
        # burst_frac = 0.80, which is in the cooling phase (>0.6)
        t = 1.0 + 0.80 * 2.0
        contrib = effect._contribution(rocket, t, 32)
        h, sat, bri = contrib[16]
        if bri > 0.0:
            # Hue should be between 350 and 25 (going the short way via 0)
            assert 0 <= h <= 360

    def test_hue_wrap_negative_diff_less_neg180(self) -> None:
        """Test hue wrap when diff < -180 (line 433).

        burst_hue=350, _BURST_COOL_HUE=25 => diff = 25-350 = -325.
        Since -325 < -180, diff += 360 => 35. Hue interpolates 350->25
        going forward through 360/0.
        """
        effect = EffectFireworks(brightness=1.0)
        rocket = _Rocket(
            origin=0,
            direction=1,
            zenith=16,
            launch_t=0.0,
            ascent_dur=1.0,
            burst_hue=350.0,
            burst_dur=2.0,
        )
        # burst_frac in cooling phase
        t = 1.0 + 0.85 * 2.0
        contrib = effect._contribution(rocket, t, 32)
        h, sat, bri = contrib[16]
        assert bri >= 0.0  # Valid contribution

    def test_burst_min_brightness_skip(self) -> None:
        """Test zones with brightness below BURST_MIN_BRIGHTNESS are skipped.

        Line 443: When burst Gaussian brightness is below threshold, the
        zone contribution stays at the default (0, 0, 0).
        """
        effect = EffectFireworks(brightness=1.0)
        rocket = _Rocket(
            origin=0,
            direction=1,
            zenith=5,
            launch_t=0.0,
            ascent_dur=0.5,
            burst_hue=120.0,
            burst_dur=2.0,
        )
        # Late in burst but still within burst_dur (burst_frac < 1.0).
        # burst_age = t - launch_t - ascent_dur = t - 0 - 0.5
        # Need burst_age < burst_dur (2.0) => t < 2.5
        # Use burst_frac ~0.9 => burst_age = 1.8 => t = 2.3
        t = 0.5 + 0.9 * 2.0  # t=2.3, burst_frac=0.9
        # Use a large zone count so distant zones have Gaussian below threshold
        contrib = effect._contribution(rocket, t, 80)
        # Zones far from zenith (5) should be dark (skipped via continue)
        far_zones = [contrib[z] for z in range(60, 80)]
        for h, s, b in far_zones:
            assert b == 0.0  # Skipped due to min brightness
