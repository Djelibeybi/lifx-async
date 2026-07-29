"""Tests for MirrorLight device class."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lifx.color import HSBK
from lifx.devices.detection import get_device_class_for_product
from lifx.devices.mirror import MirrorLight
from lifx.exceptions import LifxError
from lifx.products import get_mirror_layout, get_product, is_mirror_product
from lifx.products.quirks import MIRROR_ZONE_MAP
from lifx.theme import Theme

FRONT_ZONE_COUNT = 25
BACK_ZONE_COUNT = 25
#: The Mirror is a 4x13 matrix, so the Set64 buffer is 52 positions long.
BUFFER_SIZE = 52
FRONT_POSITIONS = get_mirror_layout(267).front_positions
BACK_POSITIONS = get_mirror_layout(267).back_positions
UNUSED_POSITIONS = tuple(
    position for position, zone in enumerate(MIRROR_ZONE_MAP) if zone < 0
)

WHITE = HSBK(hue=0, saturation=0.0, brightness=1.0, kelvin=3500)


def _buffer(front: list[HSBK], back: list[HSBK], fill: HSBK = WHITE) -> list[HSBK]:
    """Build a 52-position Set64 buffer from front and back component colours."""
    buffer = [fill] * BUFFER_SIZE
    for position, color in zip(FRONT_POSITIONS, front):
        buffer[position] = color
    for position, color in zip(BACK_POSITIONS, back):
        buffer[position] = color
    return buffer


def _front_of(buffer: list[HSBK]) -> list[HSBK]:
    """Read the front component out of a Set64 buffer."""
    return [buffer[position] for position in FRONT_POSITIONS]


def _back_of(buffer: list[HSBK]) -> list[HSBK]:
    """Read the back component out of a Set64 buffer."""
    return [buffer[position] for position in BACK_POSITIONS]


def _make_mock_state(power: int = 65535) -> MagicMock:
    """Create a mock MirrorLightState with correct defaults."""
    state = MagicMock()
    state.power = power
    state.stored_front_colors = None
    state.stored_back_colors = None
    state.last_front_colors = None
    state.last_back_colors = None
    return state


def _mirror(product: int = 267, power: int = 65535) -> MirrorLight:
    """Create a Mirror instance with mocked connection and tile colours."""
    mirror = MirrorLight(serial="d073d5010203", ip="192.168.1.100")
    mirror.connection = AsyncMock()
    mirror._state = _make_mock_state(power)
    mirror.set_matrix_colors = AsyncMock()
    mirror.get_all_tile_colors = AsyncMock(return_value=[[WHITE] * BUFFER_SIZE])
    mirror.get_power = AsyncMock(return_value=power)
    mirror._save_state_to_file = MagicMock()
    mirror._version = MagicMock()
    mirror._version.product = product
    return mirror


class TestMirrorProductDetection:
    """Tests for Mirror product identification and routing."""

    @pytest.mark.parametrize("product", [267, 268])
    def test_mirror_products_are_recognised(self, product: int) -> None:
        """Test that both Mirror products carry a component layout."""
        assert is_mirror_product(product) is True

        layout = get_mirror_layout(product)
        assert layout is not None
        assert (layout.width, layout.height) == (4, 13)
        assert layout.buffer_size == BUFFER_SIZE
        assert layout.zone_count == 50
        assert len(layout.front_positions) == 25
        assert len(layout.back_positions) == 25

    @pytest.mark.parametrize("product", [267, 268])
    def test_detection_routes_mirror_products(self, product: int) -> None:
        """Test that Mirror products resolve to MirrorLight, not MatrixLight."""
        assert (
            get_device_class_for_product(product, get_product(product)) is MirrorLight
        )

    def test_non_mirror_product_has_no_layout(self) -> None:
        """Test that a non-Mirror matrix product has no Mirror layout."""
        assert is_mirror_product(176) is False
        assert get_mirror_layout(176) is None

    def test_zone_map_covers_every_zone_once(self) -> None:
        """Test that the buffer map holds zones 0-49 exactly once."""
        mapped = [zone for zone in MIRROR_ZONE_MAP if zone >= 0]

        assert len(MIRROR_ZONE_MAP) == BUFFER_SIZE
        assert sorted(mapped) == list(range(50))
        assert len(UNUSED_POSITIONS) == 2

    def test_component_positions_follow_the_zone_map(self) -> None:
        """Test that positions are ordered by zone, not by buffer index."""
        layout = get_mirror_layout(267)
        assert layout is not None

        for zone, position in enumerate(layout.front_positions):
            assert MIRROR_ZONE_MAP[position] == zone
        for offset, position in enumerate(layout.back_positions):
            assert MIRROR_ZONE_MAP[position] == offset + 25

        # Front and back never share a buffer position
        assert not set(layout.front_positions) & set(layout.back_positions)

    def test_zone_properties(self) -> None:
        """Test the component position properties and counts."""
        mirror = _mirror()

        assert mirror.front_positions == FRONT_POSITIONS
        assert mirror.back_positions == BACK_POSITIONS
        assert mirror.front_zone_count == FRONT_ZONE_COUNT
        assert mirror.back_zone_count == BACK_ZONE_COUNT

    def test_zone_properties_without_version_raise(self) -> None:
        """Test that zone properties need the device version."""
        mirror = MirrorLight(serial="d073d5010203", ip="192.168.1.100")

        with pytest.raises(LifxError, match="Device version not available"):
            _ = mirror.front_positions

    def test_zone_properties_reject_non_mirror_product(self) -> None:
        """Test that zone properties reject a non-Mirror product."""
        mirror = _mirror(product=176)

        with pytest.raises(LifxError, match="is not a Mirror light"):
            _ = mirror.back_positions


class TestMirrorGetMethods:
    """Tests for reading component colours."""

    async def test_get_front_colors(self) -> None:
        """Test that front colours come from the first 25 zones."""
        mirror = _mirror()
        front = [
            HSBK(hue=i * 4, saturation=1.0, brightness=1.0, kelvin=3500)
            for i in range(25)
        ]
        back = [HSBK(hue=200, saturation=0.5, brightness=0.5, kelvin=2700)] * 25
        mirror.get_all_tile_colors = AsyncMock(return_value=[_buffer(front, back)])

        assert await mirror.get_front_colors() == front

    async def test_get_back_colors(self) -> None:
        """Test that back colours come from the last 25 zones."""
        mirror = _mirror()
        front = [WHITE] * 25
        back = [
            HSBK(hue=i * 4, saturation=1.0, brightness=1.0, kelvin=3500)
            for i in range(25)
        ]
        mirror.get_all_tile_colors = AsyncMock(return_value=[_buffer(front, back)])

        assert await mirror.get_back_colors() == back


class TestMirrorSetMethods:
    """Tests for writing component colours."""

    async def test_set_front_colors_single_color(self) -> None:
        """Test that a single colour fills every front zone."""
        mirror = _mirror()
        color = HSBK(hue=30, saturation=0.2, brightness=0.5, kelvin=2700)

        await mirror.set_front_colors(color, duration=1.0)

        written = mirror.set_matrix_colors.call_args.args[1]
        assert len(written) == BUFFER_SIZE
        assert _front_of(written) == [color] * 25
        assert mirror.set_matrix_colors.call_args.kwargs["duration"] == 1000

    async def test_set_front_colors_leaves_back_untouched(self) -> None:
        """Test that writing the front does not disturb the back zones."""
        mirror = _mirror()
        back = [HSBK(hue=200, saturation=1.0, brightness=0.4, kelvin=2700)] * 25
        mirror.get_all_tile_colors = AsyncMock(
            return_value=[_buffer([WHITE] * 25, back)]
        )
        color = HSBK(hue=30, saturation=0.2, brightness=0.5, kelvin=2700)

        await mirror.set_front_colors(color)

        written = mirror.set_matrix_colors.call_args.args[1]
        assert _back_of(written) == back

    async def test_set_back_colors_leaves_front_untouched(self) -> None:
        """Test that writing the back does not disturb the front zones."""
        mirror = _mirror()
        front = [HSBK(hue=120, saturation=1.0, brightness=0.9, kelvin=3500)] * 25
        mirror.get_all_tile_colors = AsyncMock(
            return_value=[_buffer(front, [WHITE] * 25)]
        )
        color = HSBK(hue=30, saturation=0.2, brightness=0.5, kelvin=2700)

        await mirror.set_back_colors(color)

        written = mirror.set_matrix_colors.call_args.args[1]
        assert _front_of(written) == front
        assert _back_of(written) == [color] * 25

    async def test_set_front_colors_list(self) -> None:
        """Test setting each front zone individually."""
        mirror = _mirror()
        colors = [
            HSBK(hue=i * 10, saturation=1.0, brightness=1.0, kelvin=3500)
            for i in range(25)
        ]

        await mirror.set_front_colors(colors)

        written = mirror.set_matrix_colors.call_args.args[1]
        assert _front_of(written) == colors

    async def test_set_back_colors_wrong_length_raises(self) -> None:
        """Test that a mismatched colour list is rejected."""
        mirror = _mirror()

        with pytest.raises(ValueError, match="Expected 25 colors for back, got 10"):
            await mirror.set_back_colors([WHITE] * 10)

        mirror.set_matrix_colors.assert_not_called()

    async def test_set_front_colors_all_dark_raises(self) -> None:
        """Test that an entirely unlit palette is rejected."""
        mirror = _mirror()
        dark = HSBK(hue=0, saturation=0.0, brightness=0.0, kelvin=3500)

        with pytest.raises(ValueError, match="Use turn_front_off"):
            await mirror.set_front_colors(dark)

        mirror.set_matrix_colors.assert_not_called()

    async def test_set_front_colors_some_dark_allowed(self) -> None:
        """Test that a partly unlit palette is accepted."""
        mirror = _mirror()
        colors = [WHITE] * 24 + [
            HSBK(hue=0, saturation=0.0, brightness=0.0, kelvin=3500)
        ]

        await mirror.set_front_colors(colors)

        mirror.set_matrix_colors.assert_called_once()


class TestMirrorTurnOnOff:
    """Tests for per-component power control."""

    async def test_turn_back_off_zeroes_only_back(self) -> None:
        """Test that turning the back off preserves H, S, K and the front."""
        mirror = _mirror()
        front = [HSBK(hue=120, saturation=1.0, brightness=0.9, kelvin=3500)] * 25
        back = [HSBK(hue=200, saturation=0.8, brightness=0.4, kelvin=2700)] * 25
        mirror.get_all_tile_colors = AsyncMock(return_value=[_buffer(front, back)])

        await mirror.turn_back_off()

        written = mirror.set_matrix_colors.call_args.args[1]
        assert _front_of(written) == front
        assert all(c.brightness == 0 for c in _back_of(written))
        assert all(c.hue == 200 and c.kelvin == 2700 for c in _back_of(written))

    async def test_turn_front_on_while_powered_sets_colors(self) -> None:
        """Test that turning a component on with the light already on writes it."""
        mirror = _mirror(power=65535)
        color = HSBK(hue=30, saturation=0.2, brightness=0.5, kelvin=2700)

        await mirror.turn_front_on(color)

        written = mirror.set_matrix_colors.call_args.args[1]
        assert _front_of(written) == [color] * 25

    async def test_turn_front_on_while_off_zeroes_back(self) -> None:
        """Test that turning one component on from cold leaves the other dark."""
        mirror = _mirror(power=0)
        mirror.set_power = AsyncMock()
        color = HSBK(hue=30, saturation=0.2, brightness=0.5, kelvin=2700)

        await mirror.turn_front_on(color, duration=2.0)

        written = mirror.set_matrix_colors.call_args.args[1]
        assert _front_of(written) == [color] * 25
        assert all(c.brightness == 0 for c in _back_of(written))
        # Colours are written instantly, then power fades up
        assert mirror.set_matrix_colors.call_args.kwargs["duration"] == 0

    async def test_turn_back_on_uses_stored_colors(self) -> None:
        """Test that a stored palette is restored when no colour is given."""
        mirror = _mirror(power=65535)
        stored = [
            HSBK(hue=i * 10, saturation=1.0, brightness=0.6, kelvin=3500)
            for i in range(25)
        ]
        mirror._state.stored_back_colors = stored

        await mirror.turn_back_on()

        written = mirror.set_matrix_colors.call_args.args[1]
        assert _back_of(written) == stored

    async def test_turn_front_on_infers_brightness_from_back(self) -> None:
        """Test that brightness is inferred from the other component."""
        mirror = _mirror(power=65535)
        front = [HSBK(hue=0, saturation=0.0, brightness=0.0, kelvin=3500)] * 25
        back = [HSBK(hue=200, saturation=0.8, brightness=0.4, kelvin=2700)] * 25
        mirror.get_all_tile_colors = AsyncMock(return_value=[_buffer(front, back)])

        await mirror.turn_front_on()

        written = mirror.set_matrix_colors.call_args.args[1]
        assert all(
            c.brightness == pytest.approx(0.4, abs=1e-4) for c in _front_of(written)
        )

    async def test_turn_front_on_falls_back_to_default_brightness(self) -> None:
        """Test the hardcoded default when the other component is dark too."""
        mirror = _mirror(power=65535)
        dark = HSBK(hue=0, saturation=0.0, brightness=0.0, kelvin=3500)
        mirror.get_all_tile_colors = AsyncMock(return_value=[[dark] * BUFFER_SIZE])

        await mirror.turn_front_on()

        written = mirror.set_matrix_colors.call_args.args[1]
        assert all(
            c.brightness == pytest.approx(0.8, abs=1e-4) for c in _front_of(written)
        )

    async def test_turn_back_on_rejects_wrong_length(self) -> None:
        """Test that a mismatched colour list is rejected before any I/O."""
        mirror = _mirror()

        with pytest.raises(ValueError, match="Expected 25 colors for back"):
            await mirror.turn_back_on([WHITE] * 3)

        mirror.set_matrix_colors.assert_not_called()


class TestMirrorComponentThemes:
    """Tests for per-component theme application."""

    async def test_apply_front_theme_covers_front_zones(self) -> None:
        """Test that a theme is rendered onto the front ring only."""
        mirror = _mirror(power=65535)
        back = [HSBK(hue=200, saturation=1.0, brightness=0.4, kelvin=2700)] * 25
        mirror.get_all_tile_colors = AsyncMock(
            return_value=[_buffer([WHITE] * 25, back)]
        )
        theme = Theme(
            [
                HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500),
                HSBK(hue=240, saturation=1.0, brightness=1.0, kelvin=3500),
            ]
        )

        await mirror.apply_front_theme(theme)

        written = mirror.set_matrix_colors.call_args.args[1]
        # One Set64 buffer, front rewritten, back left alone
        assert len(written) == BUFFER_SIZE
        assert len(_front_of(written)) == 25
        assert _back_of(written) == back
        assert _front_of(written) != [WHITE] * 25

    async def test_apply_theme_uses_the_matrix_generator(self) -> None:
        """Test that the theme is rendered over the full 4x13 matrix."""
        mirror = _mirror(power=65535)
        theme = Theme([HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)])

        with patch("lifx.theme.generators.MatrixGenerator") as generator_class:
            generator_class.return_value.get_theme_colors.return_value = [
                [WHITE] * BUFFER_SIZE
            ]
            await mirror.apply_back_theme(theme)

        # Rendered across the whole matrix, as one tile at the origin
        generator_class.assert_called_once_with([((0, 0), (4, 13))])

    async def test_apply_back_theme_powers_on_after_writing(self) -> None:
        """Test that power_on writes colours first, then fades the light up."""
        mirror = _mirror(power=0)
        mirror.set_power = AsyncMock()
        theme = Theme([HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=3500)])

        await mirror.apply_back_theme(theme, power_on=True, duration=3.0)

        assert mirror.set_matrix_colors.call_args.kwargs["duration"] == 0
        mirror.set_power.assert_awaited_once_with(True, 3.0)


class TestMirrorStatePersistence:
    """Tests for the JSON state file."""

    def test_save_and_load_round_trip(self) -> None:
        """Test that stored component colours survive a save/load cycle."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = str(Path(tmpdir) / "mirror.json")

            saver = _mirror()
            saver._state_file = state_file
            saver._save_state_to_file = MirrorLight._save_state_to_file.__get__(saver)
            front = [HSBK(hue=10, saturation=1.0, brightness=0.5, kelvin=3500)] * 25
            back = [HSBK(hue=200, saturation=0.5, brightness=0.3, kelvin=2700)] * 25
            saver._state.stored_front_colors = front
            saver._state.stored_back_colors = back

            saver._save_state_to_file()

            document = json.loads(Path(state_file).read_text())
            assert len(document["d073d5010203"]["front"]) == 25
            assert len(document["d073d5010203"]["back"]) == 25

            loader = _mirror()
            loader._state_file = state_file
            loader._state.stored_front_colors = None
            loader._state.stored_back_colors = None

            loader._load_state_from_file()

            assert loader._state.stored_front_colors == front
            assert loader._state.stored_back_colors == back

    def test_load_ignores_wrong_zone_count(self) -> None:
        """Test that a stale palette of the wrong length is discarded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "mirror.json"
            state_file.write_text(
                json.dumps(
                    {
                        "d073d5010203": {
                            "front": [
                                {
                                    "hue": 0,
                                    "saturation": 0.0,
                                    "brightness": 1.0,
                                    "kelvin": 3500,
                                }
                            ]
                            * 10
                        }
                    }
                )
            )

            mirror = _mirror()
            mirror._state_file = str(state_file)
            mirror._state.stored_front_colors = None

            mirror._load_state_from_file()

            assert mirror._state.stored_front_colors is None

    def test_load_missing_file_is_quiet(self) -> None:
        """Test that a missing state file leaves stored colours untouched."""
        mirror = _mirror()
        mirror._state_file = "/nonexistent/path/mirror.json"
        mirror._state.stored_front_colors = None

        mirror._load_state_from_file()

        assert mirror._state.stored_front_colors is None


class TestMirrorZoneMapValidation:
    """Tests for zone map to buffer position derivation."""

    def test_missing_zone_is_rejected(self) -> None:
        """Test that a zone map with a gap is reported, not silently accepted."""
        from lifx.products.quirks import _buffer_positions

        with pytest.raises(ValueError, match="Zone 2 is missing from the zone map"):
            _buffer_positions((0, 1, -1), range(0, 3))
