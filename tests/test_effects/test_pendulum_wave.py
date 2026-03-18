"""Tests for EffectPendulumWave (pendulum wave)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.effects.base import LIFXEffect
from lifx.effects.frame_effect import FrameContext, FrameEffect
from lifx.effects.pendulum_wave import EffectPendulumWave


def test_pendulum_wave_default_parameters() -> None:
    """Test EffectPendulumWave with default parameters."""
    effect = EffectPendulumWave()

    assert effect.name == "pendulum_wave"
    assert effect.speed == 30.0
    assert effect.cycles == 8
    assert effect.hue1 == 0
    assert effect.hue2 == 240
    assert effect.saturation1 == 1.0
    assert effect.saturation2 == 1.0
    assert effect.brightness == 0.8
    assert effect.kelvin == 3500
    assert effect.zones_per_bulb == 1
    assert effect.power_on is True
    assert effect.fps == 20.0
    assert effect.duration is None


def test_pendulum_wave_custom_parameters() -> None:
    """Test EffectPendulumWave with custom parameters."""
    effect = EffectPendulumWave(
        speed=60.0,
        cycles=12,
        hue1=120,
        hue2=300,
        saturation1=0.5,
        saturation2=0.8,
        brightness=0.6,
        kelvin=5000,
        zones_per_bulb=3,
        power_on=False,
    )

    assert effect.speed == 60.0
    assert effect.cycles == 12
    assert effect.hue1 == 120
    assert effect.hue2 == 300
    assert effect.saturation1 == 0.5
    assert effect.saturation2 == 0.8
    assert effect.brightness == 0.6
    assert effect.kelvin == 5000
    assert effect.zones_per_bulb == 3
    assert effect.power_on is False


def test_pendulum_wave_invalid_speed() -> None:
    """Test EffectPendulumWave with invalid speed raises ValueError."""
    with pytest.raises(ValueError, match="Speed must be"):
        EffectPendulumWave(speed=0)

    with pytest.raises(ValueError, match="Speed must be"):
        EffectPendulumWave(speed=-1.0)


def test_pendulum_wave_invalid_cycles() -> None:
    """Test EffectPendulumWave with invalid cycles raises ValueError."""
    with pytest.raises(ValueError, match="Cycles must be"):
        EffectPendulumWave(cycles=0)

    with pytest.raises(ValueError, match="Cycles must be"):
        EffectPendulumWave(cycles=-1)


def test_pendulum_wave_invalid_hue1() -> None:
    """Test EffectPendulumWave with invalid hue1 raises ValueError."""
    with pytest.raises(ValueError, match="hue1 must be"):
        EffectPendulumWave(hue1=-1)

    with pytest.raises(ValueError, match="hue1 must be"):
        EffectPendulumWave(hue1=361)


def test_pendulum_wave_invalid_hue2() -> None:
    """Test EffectPendulumWave with invalid hue2 raises ValueError."""
    with pytest.raises(ValueError, match="hue2 must be"):
        EffectPendulumWave(hue2=-1)

    with pytest.raises(ValueError, match="hue2 must be"):
        EffectPendulumWave(hue2=361)


def test_pendulum_wave_invalid_saturation1() -> None:
    """Test EffectPendulumWave with invalid saturation1 raises ValueError."""
    with pytest.raises(ValueError, match="saturation1 must be"):
        EffectPendulumWave(saturation1=1.5)

    with pytest.raises(ValueError, match="saturation1 must be"):
        EffectPendulumWave(saturation1=-0.1)


def test_pendulum_wave_invalid_saturation2() -> None:
    """Test EffectPendulumWave with invalid saturation2 raises ValueError."""
    with pytest.raises(ValueError, match="saturation2 must be"):
        EffectPendulumWave(saturation2=1.5)

    with pytest.raises(ValueError, match="saturation2 must be"):
        EffectPendulumWave(saturation2=-0.1)


def test_pendulum_wave_invalid_brightness() -> None:
    """Test EffectPendulumWave with invalid brightness raises ValueError."""
    with pytest.raises(ValueError, match="Brightness must be"):
        EffectPendulumWave(brightness=1.5)

    with pytest.raises(ValueError, match="Brightness must be"):
        EffectPendulumWave(brightness=-0.1)


def test_pendulum_wave_invalid_kelvin() -> None:
    """Test EffectPendulumWave with invalid kelvin raises ValueError."""
    with pytest.raises(ValueError, match="Kelvin must be"):
        EffectPendulumWave(kelvin=1000)

    with pytest.raises(ValueError, match="Kelvin must be"):
        EffectPendulumWave(kelvin=10000)


def test_pendulum_wave_invalid_zones_per_bulb() -> None:
    """Test EffectPendulumWave with invalid zones_per_bulb raises ValueError."""
    with pytest.raises(ValueError, match="zones_per_bulb must be"):
        EffectPendulumWave(zones_per_bulb=0)

    with pytest.raises(ValueError, match="zones_per_bulb must be"):
        EffectPendulumWave(zones_per_bulb=-1)


class TestPendulumWaveInheritance:
    """Tests for EffectPendulumWave class hierarchy."""

    def test_is_frame_effect(self) -> None:
        """Test EffectPendulumWave extends FrameEffect."""
        effect = EffectPendulumWave()
        assert isinstance(effect, FrameEffect)

    def test_is_lifx_effect(self) -> None:
        """Test EffectPendulumWave extends LIFXEffect."""
        effect = EffectPendulumWave()
        assert isinstance(effect, LIFXEffect)


class TestPendulumWaveGenerateFrame:
    """Tests for EffectPendulumWave.generate_frame()."""

    def test_single_pixel_returns_one_color(self) -> None:
        """Test single-pixel device returns one color."""
        effect = EffectPendulumWave()
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
        effect = EffectPendulumWave()
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
        effect = EffectPendulumWave()
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
        effect = EffectPendulumWave(kelvin=5000)
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
        effect = EffectPendulumWave()
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
        effect = EffectPendulumWave()
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
        effect = EffectPendulumWave(cycles=8)
        ctx = FrameContext(
            elapsed_s=5.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)

        # Not all pixels should be the same hue when pendulums have drifted
        unique_hues = {round(c.hue, 2) for c in colors}
        assert len(unique_hues) > 1

    def test_elapsed_zero(self) -> None:
        """Test edge case with elapsed_s=0.0."""
        effect = EffectPendulumWave()
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
        effect = EffectPendulumWave(zones_per_bulb=2)
        ctx = FrameContext(
            elapsed_s=5.0,
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

    def test_all_pendulums_in_phase_at_start(self) -> None:
        """Test all pendulums start in phase at t=0 (all at sin(0)=0)."""
        effect = EffectPendulumWave(speed=30.0, cycles=8)
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=8,
            canvas_width=8,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)

        # At t=0, all sin() values are 0, so all blends are 0.5 (midpoint)
        # All colors should be identical
        for color in colors:
            assert color == colors[0]

    def test_realignment_at_speed_boundary(self) -> None:
        """Test first and last pendulums complete integer oscillations at t=speed.

        At t=speed, pendulum 0 has frequency ``cycles`` (integer oscillations)
        so sin(2pi * cycles) = 0, matching the start. The intermediate
        pendulums have non-integer frequencies so they won't perfectly match,
        but the first pendulum always realigns exactly.
        """
        effect = EffectPendulumWave(speed=30.0, cycles=8)
        ctx_start = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=8,
            canvas_width=8,
            canvas_height=1,
        )
        ctx_end = FrameContext(
            elapsed_s=30.0,
            device_index=0,
            pixel_count=8,
            canvas_width=8,
            canvas_height=1,
        )
        colors_start = effect.generate_frame(ctx_start)
        colors_end = effect.generate_frame(ctx_end)

        # First pendulum (zone 0) has freq = cycles (integer), so it
        # completes exactly `cycles` oscillations and returns to start.
        assert abs(colors_start[0].hue - colors_end[0].hue) < 0.01
        assert abs(colors_start[0].brightness - colors_end[0].brightness) < 0.01

    def test_mid_cycle_shows_variation(self) -> None:
        """Test mid-cycle produces varied colors across pendulums."""
        effect = EffectPendulumWave(speed=30.0, cycles=8)
        # At mid-cycle, pendulums should be maximally out of phase
        ctx = FrameContext(
            elapsed_s=15.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)

        # Should have significant hue variation
        hues = [c.hue for c in colors]
        hue_range = max(hues) - min(hues)
        assert hue_range > 10  # Some meaningful spread

    def test_brightness_modulation_extremes(self) -> None:
        """Test brightness is modulated by displacement magnitude."""
        effect = EffectPendulumWave(speed=30.0, cycles=8, brightness=1.0)
        # Use a time where pendulums have varied displacements
        ctx = FrameContext(
            elapsed_s=5.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        brightnesses = [c.brightness for c in colors]

        # Not all brightnesses should be the same (displacement varies)
        assert len(set(round(b, 4) for b in brightnesses)) > 1

        # Max brightness should not exceed configured brightness
        for b in brightnesses:
            assert b <= 1.0 + 1e-9

    def test_single_bulb_oscillates(self) -> None:
        """Test single-pixel device oscillates over time."""
        effect = EffectPendulumWave(speed=30.0, cycles=8)
        ctx_t0 = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=1,
            canvas_width=1,
            canvas_height=1,
        )
        ctx_t1 = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=1,
            canvas_width=1,
            canvas_height=1,
        )
        colors_t0 = effect.generate_frame(ctx_t0)
        colors_t1 = effect.generate_frame(ctx_t1)

        # Single bulb uses base cycles frequency, should change over time
        assert colors_t0[0] != colors_t1[0]


class TestPendulumWaveFrameLoop:
    """Tests for EffectPendulumWave running via FrameEffect frame loop."""

    @pytest.mark.asyncio
    async def test_sends_frames_via_animator(self) -> None:
        """Test pendulum wave sends frames through animator.send_frame."""
        effect = EffectPendulumWave()

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
async def test_pendulum_wave_from_poweroff() -> None:
    """Test from_poweroff_hsbk returns dim midpoint color."""
    effect = EffectPendulumWave(hue1=0, hue2=240, kelvin=5000)
    light = MagicMock()
    result = await effect.from_poweroff_hsbk(light)

    assert result.brightness == 0.0
    assert result.kelvin == 5000


@pytest.mark.asyncio
async def test_pendulum_wave_is_light_compatible_with_color() -> None:
    """Test is_light_compatible returns True for color lights."""
    effect = EffectPendulumWave()
    light = MagicMock()
    capabilities = MagicMock()
    capabilities.has_color = True
    light.capabilities = capabilities

    assert await effect.is_light_compatible(light) is True


@pytest.mark.asyncio
async def test_pendulum_wave_is_light_compatible_without_color() -> None:
    """Test is_light_compatible returns False for non-color lights."""
    effect = EffectPendulumWave()
    light = MagicMock()
    capabilities = MagicMock()
    capabilities.has_color = False
    light.capabilities = capabilities

    assert await effect.is_light_compatible(light) is False


@pytest.mark.asyncio
async def test_pendulum_wave_is_light_compatible_none_capabilities() -> None:
    """Test is_light_compatible loads capabilities when None."""
    effect = EffectPendulumWave()
    light = MagicMock()
    light.capabilities = None

    async def ensure_caps() -> None:
        caps = MagicMock()
        caps.has_color = True
        light.capabilities = caps

    light.ensure_capabilities = AsyncMock(side_effect=ensure_caps)

    assert await effect.is_light_compatible(light) is True
    light.ensure_capabilities.assert_called_once()


def test_pendulum_wave_inherit_prestate() -> None:
    """Test inherit_prestate returns True for EffectPendulumWave."""
    effect = EffectPendulumWave()
    assert effect.inherit_prestate(EffectPendulumWave()) is True
    assert effect.inherit_prestate(MagicMock()) is False


def test_pendulum_wave_repr() -> None:
    """Test EffectPendulumWave string representation."""
    effect = EffectPendulumWave(speed=60.0, cycles=12, hue1=120, hue2=300)
    repr_str = repr(effect)

    assert "EffectPendulumWave" in repr_str
    assert "speed=60.0" in repr_str
    assert "cycles=12" in repr_str
    assert "hue1=120" in repr_str
    assert "hue2=300" in repr_str
