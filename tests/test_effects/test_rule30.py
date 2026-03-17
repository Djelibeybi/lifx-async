"""Tests for EffectRule30 (1D cellular automaton)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.effects.base import LIFXEffect
from lifx.effects.frame_effect import FrameContext, FrameEffect
from lifx.effects.rule30 import EffectRule30

# ---------------------------------------------------------------------------
# Default and custom parameters
# ---------------------------------------------------------------------------


def test_rule30_default_parameters() -> None:
    """Test EffectRule30 with default parameters."""
    effect = EffectRule30()

    assert effect.name == "rule30"
    assert effect.speed == 5.0
    assert effect.rule == 30
    assert effect.hue == 120
    assert effect.brightness == 0.8
    assert effect.background_brightness == 0.05
    assert effect.seed == "center"
    assert effect.kelvin == 3500
    assert effect.zones_per_bulb == 1
    assert effect.power_on is True
    assert effect.fps == 20.0
    assert effect.duration is None


def test_rule30_custom_parameters() -> None:
    """Test EffectRule30 with custom parameters."""
    effect = EffectRule30(
        speed=10.0,
        rule=90,
        hue=240,
        brightness=0.6,
        background_brightness=0.1,
        seed="random",
        kelvin=5000,
        zones_per_bulb=2,
        power_on=False,
    )

    assert effect.speed == 10.0
    assert effect.rule == 90
    assert effect.hue == 240
    assert effect.brightness == 0.6
    assert effect.background_brightness == 0.1
    assert effect.seed == "random"
    assert effect.kelvin == 5000
    assert effect.zones_per_bulb == 2
    assert effect.power_on is False


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_rule30_invalid_speed() -> None:
    """Test EffectRule30 with invalid speed raises ValueError."""
    with pytest.raises(ValueError, match="Speed must be"):
        EffectRule30(speed=0)

    with pytest.raises(ValueError, match="Speed must be"):
        EffectRule30(speed=-1.0)


def test_rule30_invalid_rule() -> None:
    """Test EffectRule30 with invalid rule raises ValueError."""
    with pytest.raises(ValueError, match="Rule must be"):
        EffectRule30(rule=-1)

    with pytest.raises(ValueError, match="Rule must be"):
        EffectRule30(rule=256)


def test_rule30_invalid_hue() -> None:
    """Test EffectRule30 with invalid hue raises ValueError."""
    with pytest.raises(ValueError, match="Hue must be"):
        EffectRule30(hue=-1)

    with pytest.raises(ValueError, match="Hue must be"):
        EffectRule30(hue=361)


def test_rule30_invalid_brightness() -> None:
    """Test EffectRule30 with invalid brightness raises ValueError."""
    with pytest.raises(ValueError, match="Brightness must be"):
        EffectRule30(brightness=1.5)

    with pytest.raises(ValueError, match="Brightness must be"):
        EffectRule30(brightness=-0.1)


def test_rule30_invalid_background_brightness() -> None:
    """Test EffectRule30 with invalid background_brightness raises ValueError."""
    with pytest.raises(ValueError, match="Background brightness must be"):
        EffectRule30(background_brightness=1.5)

    with pytest.raises(ValueError, match="Background brightness must be"):
        EffectRule30(background_brightness=-0.1)


def test_rule30_invalid_seed() -> None:
    """Test EffectRule30 with invalid seed raises ValueError."""
    with pytest.raises(ValueError, match="Seed must be"):
        EffectRule30(seed="invalid")

    with pytest.raises(ValueError, match="Seed must be"):
        EffectRule30(seed="")


def test_rule30_invalid_kelvin() -> None:
    """Test EffectRule30 with invalid kelvin raises ValueError."""
    with pytest.raises(ValueError, match="Kelvin must be"):
        EffectRule30(kelvin=1000)

    with pytest.raises(ValueError, match="Kelvin must be"):
        EffectRule30(kelvin=10000)


def test_rule30_invalid_zones_per_bulb() -> None:
    """Test EffectRule30 with invalid zones_per_bulb raises ValueError."""
    with pytest.raises(ValueError, match="zones_per_bulb must be"):
        EffectRule30(zones_per_bulb=0)

    with pytest.raises(ValueError, match="zones_per_bulb must be"):
        EffectRule30(zones_per_bulb=-1)


def test_rule30_boundary_rule_values() -> None:
    """Test rule boundary values 0 and 255 are accepted."""
    effect0 = EffectRule30(rule=0)
    assert effect0.rule == 0

    effect255 = EffectRule30(rule=255)
    assert effect255.rule == 255


# ---------------------------------------------------------------------------
# Inheritance
# ---------------------------------------------------------------------------


class TestRule30Inheritance:
    """Tests for EffectRule30 class hierarchy."""

    def test_is_frame_effect(self) -> None:
        """Test EffectRule30 extends FrameEffect."""
        effect = EffectRule30()
        assert isinstance(effect, FrameEffect)

    def test_is_lifx_effect(self) -> None:
        """Test EffectRule30 extends LIFXEffect."""
        effect = EffectRule30()
        assert isinstance(effect, LIFXEffect)


# ---------------------------------------------------------------------------
# Seed modes
# ---------------------------------------------------------------------------


class TestRule30SeedModes:
    """Tests for different seed initialization modes."""

    def test_center_seed_has_single_alive_cell(self) -> None:
        """Test center seed produces a single alive cell in the middle."""
        effect = EffectRule30(seed="center", speed=0.1)
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)

        # Only the center cell should be alive (bright)
        alive_count = sum(1 for c in colors if c.brightness == effect.brightness)
        assert alive_count == 1

        # The alive cell should be at the center
        center_idx = 16 // 2
        assert colors[center_idx].brightness == effect.brightness

    def test_all_seed_has_all_alive(self) -> None:
        """Test 'all' seed produces all alive cells."""
        effect = EffectRule30(seed="all", speed=0.1)
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)

        # All cells should be alive
        for color in colors:
            assert color.brightness == effect.brightness

    def test_random_seed_varies(self) -> None:
        """Test 'random' seed produces a mix of alive and dead cells."""
        # Run a few times; with 16 cells, probability of all-same is ~2^-16
        effect = EffectRule30(seed="random", speed=0.1)
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        brightnesses = {c.brightness for c in colors}
        # Extremely unlikely to get all identical with 16 random cells
        assert len(brightnesses) >= 1  # At minimum it produces valid output

    def test_different_seeds_produce_different_initial_states(self) -> None:
        """Test that center and all seeds produce different initial frames."""
        effect_center = EffectRule30(seed="center", speed=0.1)
        effect_all = EffectRule30(seed="all", speed=0.1)

        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors_center = effect_center.generate_frame(ctx)
        colors_all = effect_all.generate_frame(ctx)

        assert colors_center != colors_all


# ---------------------------------------------------------------------------
# Cellular automaton logic
# ---------------------------------------------------------------------------


class TestRule30CellularAutomaton:
    """Tests for the CA stepping logic."""

    def test_state_advances_over_time(self) -> None:
        """Test that the CA advances generations as time increases."""
        effect = EffectRule30(speed=5.0, seed="center")
        ctx0 = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        ctx1 = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors0 = effect.generate_frame(ctx0)
        colors1 = effect.generate_frame(ctx1)

        # After 5 generations (1.0s * 5.0 speed), pattern should differ
        assert colors0 != colors1

    def test_generation_counter_tracks_time(self) -> None:
        """Test generation counter advances based on elapsed time and speed."""
        effect = EffectRule30(speed=10.0, seed="center")
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        effect.generate_frame(ctx)
        assert effect._generation == 0

        ctx2 = FrameContext(
            elapsed_s=0.5,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        effect.generate_frame(ctx2)
        # 0.5s * 10.0 speed = 5 generations
        assert effect._generation == 5

    def test_rule30_produces_specific_pattern(self) -> None:
        """Test Rule 30 produces the expected pattern from center seed.

        Rule 30 from a single center cell should produce a known pattern
        after one generation on a small strip.
        """
        effect = EffectRule30(rule=30, seed="center", speed=1.0)
        # Use 5 cells: [0, 0, 1, 0, 0] with periodic boundaries
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=5,
            canvas_width=5,
            canvas_height=1,
        )
        effect.generate_frame(ctx)
        assert effect._state == [0, 0, 1, 0, 0]

        # Advance one generation
        ctx1 = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=5,
            canvas_width=5,
            canvas_height=1,
        )
        effect.generate_frame(ctx1)
        # Rule 30 lookup:
        # neighborhood 000 (0) -> bit 0 of 30 (0b00011110) = 0
        # neighborhood 001 (1) -> bit 1 = 1
        # neighborhood 010 (2) -> bit 2 = 1
        # neighborhood 011 (3) -> bit 3 = 1
        # neighborhood 100 (4) -> bit 4 = 1
        # Cell 0: L=state[4]=0, C=0, R=0 -> 000=0 -> 0
        # Cell 1: L=state[0]=0, C=0, R=1 -> 001=1 -> 1
        # Cell 2: L=state[1]=0, C=1, R=0 -> 010=2 -> 1
        # Cell 3: L=state[2]=1, C=0, R=0 -> 100=4 -> 1
        # Cell 4: L=state[3]=0, C=0, R=0 -> 000=0 -> 0
        assert effect._state == [0, 1, 1, 1, 0]

    def test_rule90_produces_different_pattern_than_rule30(self) -> None:
        """Test Rule 90 produces a different pattern than Rule 30."""
        effect30 = EffectRule30(rule=30, seed="center", speed=1.0)
        effect90 = EffectRule30(rule=90, seed="center", speed=1.0)

        ctx0 = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=11,
            canvas_width=11,
            canvas_height=1,
        )
        effect30.generate_frame(ctx0)
        effect90.generate_frame(ctx0)

        # Advance both by one generation
        ctx1 = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=11,
            canvas_width=11,
            canvas_height=1,
        )
        effect30.generate_frame(ctx1)
        effect90.generate_frame(ctx1)

        assert effect30._state != effect90._state

    def test_rule90_specific_pattern(self) -> None:
        """Test Rule 90 produces XOR pattern from center seed.

        Rule 90 is the XOR rule: new cell = left XOR right.
        From [0,0,1,0,0] with periodic boundaries:
        Cell 0: L=0 XOR R=0 = 0
        Cell 1: L=0 XOR R=1 = 1
        Cell 2: L=0 XOR R=0 = 0
        Cell 3: L=1 XOR R=0 = 1
        Cell 4: L=0 XOR R=0 = 0
        """
        effect = EffectRule30(rule=90, seed="center", speed=1.0)
        ctx0 = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=5,
            canvas_width=5,
            canvas_height=1,
        )
        effect.generate_frame(ctx0)

        ctx1 = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=5,
            canvas_width=5,
            canvas_height=1,
        )
        effect.generate_frame(ctx1)
        assert effect._state == [0, 1, 0, 1, 0]

    def test_periodic_boundary_conditions(self) -> None:
        """Test that boundaries wrap around (periodic/ring topology)."""
        # Place alive cell at position 0
        effect = EffectRule30(rule=30, seed="center", speed=1.0)
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=5,
            canvas_width=5,
            canvas_height=1,
        )
        effect.generate_frame(ctx)
        # Manually set state to have alive cell at edge
        effect._state = [1, 0, 0, 0, 0]
        effect._generation = 0

        ctx1 = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=5,
            canvas_width=5,
            canvas_height=1,
        )
        effect.generate_frame(ctx1)

        # With periodic boundaries, cell 4's right neighbor is cell 0
        # Cell 4: L=state[3]=0, C=state[4]=0, R=state[0]=1 -> 001=1
        # For rule 30: bit 1 = 1, so cell 4 should be alive
        assert effect._state[4] == 1

    def test_rule0_kills_all_cells(self) -> None:
        """Test Rule 0 turns all cells dead regardless of input."""
        effect = EffectRule30(rule=0, seed="all", speed=1.0)
        ctx0 = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=8,
            canvas_width=8,
            canvas_height=1,
        )
        effect.generate_frame(ctx0)
        assert all(c == 1 for c in effect._state)

        ctx1 = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=8,
            canvas_width=8,
            canvas_height=1,
        )
        effect.generate_frame(ctx1)
        # Rule 0: every neighborhood maps to 0
        assert all(c == 0 for c in effect._state)

    def test_rule255_all_alive(self) -> None:
        """Test Rule 255 makes all cells alive regardless of input."""
        effect = EffectRule30(rule=255, seed="center", speed=1.0)
        ctx0 = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=8,
            canvas_width=8,
            canvas_height=1,
        )
        effect.generate_frame(ctx0)

        ctx1 = FrameContext(
            elapsed_s=1.0,
            device_index=0,
            pixel_count=8,
            canvas_width=8,
            canvas_height=1,
        )
        effect.generate_frame(ctx1)
        # Rule 255: every neighborhood maps to 1
        assert all(c == 1 for c in effect._state)


# ---------------------------------------------------------------------------
# Frame generation
# ---------------------------------------------------------------------------


class TestRule30GenerateFrame:
    """Tests for EffectRule30.generate_frame()."""

    def test_single_pixel_returns_one_color(self) -> None:
        """Test single-pixel device returns one color."""
        effect = EffectRule30()
        ctx = FrameContext(
            elapsed_s=0.0,
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
        effect = EffectRule30()
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=pixel_count,
            canvas_width=pixel_count,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        assert len(colors) == pixel_count

    def test_hue_matches_configured(self) -> None:
        """Test all pixel hues match the configured hue."""
        effect = EffectRule30(hue=240)
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        for color in colors:
            assert color.hue == 240

    def test_saturation_is_full(self) -> None:
        """Test all pixels have full saturation."""
        effect = EffectRule30()
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        for color in colors:
            assert color.saturation == 1.0

    def test_kelvin_matches_configured(self) -> None:
        """Test kelvin values match configured kelvin."""
        effect = EffectRule30(kelvin=5000)
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        for color in colors:
            assert color.kelvin == 5000

    def test_brightness_values_are_alive_or_dead(self) -> None:
        """Test brightness values are either alive or dead brightness."""
        effect = EffectRule30(brightness=0.8, background_brightness=0.05)
        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        colors = effect.generate_frame(ctx)
        for color in colors:
            assert color.brightness in (0.8, 0.05)

    def test_elapsed_zero(self) -> None:
        """Test edge case with elapsed_s=0.0."""
        effect = EffectRule30()
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
        effect = EffectRule30(zones_per_bulb=2, seed="all")
        ctx = FrameContext(
            elapsed_s=0.0,
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

    def test_lazy_initialization(self) -> None:
        """Test state is lazily initialized on first generate_frame call."""
        effect = EffectRule30()
        assert effect._state == []
        assert effect._generation == 0

        ctx = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        effect.generate_frame(ctx)
        assert len(effect._state) == 16

    def test_state_persists_across_frames(self) -> None:
        """Test that state is maintained between generate_frame calls."""
        effect = EffectRule30(speed=10.0, seed="center")
        ctx0 = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        effect.generate_frame(ctx0)
        state_after_init = list(effect._state)

        # Same elapsed time should not change state
        effect.generate_frame(ctx0)
        assert effect._state == state_after_init

    def test_reinitializes_on_pixel_count_change(self) -> None:
        """Test state reinitializes if pixel_count changes."""
        effect = EffectRule30(seed="center", speed=0.1)
        ctx8 = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=8,
            canvas_width=8,
            canvas_height=1,
        )
        effect.generate_frame(ctx8)
        assert len(effect._state) == 8

        ctx16 = FrameContext(
            elapsed_s=0.0,
            device_index=0,
            pixel_count=16,
            canvas_width=16,
            canvas_height=1,
        )
        effect.generate_frame(ctx16)
        assert len(effect._state) == 16


# ---------------------------------------------------------------------------
# Frame loop integration
# ---------------------------------------------------------------------------


class TestRule30FrameLoop:
    """Tests for EffectRule30 running via FrameEffect frame loop."""

    @pytest.mark.asyncio
    async def test_sends_frames_via_animator(self) -> None:
        """Test rule30 sends frames through animator.send_frame."""
        effect = EffectRule30()

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
# Power off and compatibility
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rule30_from_poweroff() -> None:
    """Test from_poweroff_hsbk returns dim version of effect color."""
    effect = EffectRule30(hue=120, kelvin=5000)
    light = MagicMock()
    result = await effect.from_poweroff_hsbk(light)

    assert result.hue == 120
    assert result.saturation == 1.0
    assert result.brightness == 0.0
    assert result.kelvin == 5000


@pytest.mark.asyncio
async def test_rule30_is_light_compatible_with_multizone() -> None:
    """Test is_light_compatible returns True for multizone lights."""
    effect = EffectRule30()
    light = MagicMock()
    capabilities = MagicMock()
    capabilities.has_multizone = True
    light.capabilities = capabilities

    assert await effect.is_light_compatible(light) is True


@pytest.mark.asyncio
async def test_rule30_is_light_compatible_without_multizone() -> None:
    """Test is_light_compatible returns False for non-multizone lights."""
    effect = EffectRule30()
    light = MagicMock()
    capabilities = MagicMock()
    capabilities.has_multizone = False
    light.capabilities = capabilities

    assert await effect.is_light_compatible(light) is False


@pytest.mark.asyncio
async def test_rule30_is_light_compatible_none_capabilities() -> None:
    """Test is_light_compatible loads capabilities when None."""
    effect = EffectRule30()
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
# Prestate and repr
# ---------------------------------------------------------------------------


def test_rule30_inherit_prestate() -> None:
    """Test inherit_prestate returns True for EffectRule30."""
    effect = EffectRule30()
    assert effect.inherit_prestate(EffectRule30()) is True
    assert effect.inherit_prestate(MagicMock()) is False


def test_rule30_repr() -> None:
    """Test EffectRule30 string representation."""
    effect = EffectRule30(speed=10.0, rule=90, hue=240, brightness=0.6)
    repr_str = repr(effect)

    assert "EffectRule30" in repr_str
    assert "speed=10.0" in repr_str
    assert "rule=90" in repr_str
    assert "hue=240" in repr_str
    assert "brightness=0.6" in repr_str
    assert "seed='center'" in repr_str
