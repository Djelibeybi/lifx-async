"""Tests for MirrorLight device class."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from lifx.color import HSBK
from lifx.devices.component_state import WRITE_SETTLE_MARGIN
from lifx.devices.detection import get_device_class_for_product
from lifx.devices.matrix import MatrixLight
from lifx.devices.mirror import MirrorLight, MirrorLightState
from lifx.exceptions import LifxError
from lifx.products import get_mirror_layout, get_product, is_mirror_product
from lifx.products.quirks import MIRROR_ZONE_MAP, _buffer_positions
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
    mirror._save_state_to_file = AsyncMock()
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


class TestMirrorTransitions:
    """Tests for writes that land while an earlier transition is running."""

    LIT = HSBK(hue=120, saturation=1.0, brightness=0.9, kelvin=3500)
    AMBER = HSBK(hue=30, saturation=0.4, brightness=0.3, kelvin=2700)

    async def test_switch_mid_fade_carries_the_other_target(self) -> None:
        """Test that the second write keeps the first component heading to 0.

        The device reports the front still lit while it fades out. Rebuilding
        the tile from that would pin the front on; the write must carry the
        front's target instead.
        """
        mirror = _mirror()
        lit = _buffer([self.LIT] * 25, [self.LIT] * 25)
        mirror.get_all_tile_colors = AsyncMock(return_value=[lit])

        await mirror.turn_front_off(duration=1.0)
        await mirror.turn_back_on(self.AMBER, duration=1.0)

        written = mirror.set_matrix_colors.call_args.args[1]
        assert all(c.brightness == 0 for c in _front_of(written))
        assert _back_of(written) == [self.AMBER] * 25
        mirror.get_all_tile_colors.assert_awaited_once()

    async def test_device_is_read_again_once_the_fade_settles(self) -> None:
        """Test that a remembered tile expires, so outside changes are seen."""
        mirror = _mirror()
        lit = _buffer([self.LIT] * 25, [self.LIT] * 25)
        mirror.get_all_tile_colors = AsyncMock(return_value=[lit])

        with patch(
            "lifx.devices.component_state.time.monotonic", return_value=100.0
        ) as clock:
            await mirror.turn_front_off(duration=1.0)
            clock.return_value = 100.0 + 1.0 + WRITE_SETTLE_MARGIN
            await mirror.set_back_colors(self.AMBER, duration=1.0)

        assert mirror.get_all_tile_colors.await_count == 2

    async def test_set_color_fade_is_carried_into_a_component_write(self) -> None:
        """Test that a component call during set_color's fade keeps its target.

        Rebuilding from the in-flight colours would freeze the front part way
        through the set_color fade.
        """
        mirror = _mirror()
        mirror._device_chain = [MagicMock(total_zones=BUFFER_SIZE)]
        lit = _buffer([self.LIT] * 25, [self.LIT] * 25)
        mirror.get_all_tile_colors = AsyncMock(return_value=[lit])

        with patch("lifx.devices.light.Light.set_color", new_callable=AsyncMock):
            await mirror.set_color(WHITE, duration=4.0)
        await mirror.set_back_colors(self.AMBER)

        written = mirror.set_matrix_colors.call_args.args[1]
        assert _front_of(written) == [WHITE] * 25
        assert _back_of(written) == [self.AMBER] * 25
        mirror.get_all_tile_colors.assert_not_awaited()

    async def test_inherited_tile_write_forgets_the_remembered_tile(self) -> None:
        """Test that a raw Set64 is not undone by the next component write."""
        mirror = _mirror()
        lit = _buffer([self.LIT] * 25, [self.LIT] * 25)
        mirror.get_all_tile_colors = AsyncMock(return_value=[lit])

        await mirror.set_front_colors(self.AMBER, duration=2.0)
        # An inherited MatrixLight write, sent for real through the connection
        await MatrixLight.set64(
            mirror,
            tile_index=0,
            length=1,
            x=0,
            y=0,
            width=4,
            duration=0,
            colors=[WHITE] * BUFFER_SIZE,
        )
        await mirror.set_back_colors(self.AMBER)

        assert mirror.get_all_tile_colors.await_count == 2

    async def test_pending_power_on_is_trusted_for_the_margin_only(self) -> None:
        """Test that a long power-on fade does not hide a later power-off.

        GetPower reports a power-on straight away, so after the settle margin
        the device is asked again even though the fade is still running.
        """
        mirror = _mirror(power=0)

        with patch(
            "lifx.devices.component_state.time.monotonic", return_value=100.0
        ) as clock:
            mirror._record_power(True, 30.0)
            assert await mirror._power_for_update() == 65535
            mirror.get_power.assert_not_awaited()

            clock.return_value = 100.0 + WRITE_SETTLE_MARGIN
            assert await mirror._power_for_update() == 0
            mirror.get_power.assert_awaited_once()

    async def test_power_for_update_refreshes_cached_power(self) -> None:
        """Test that the power just fetched feeds the component on flags."""
        mirror = _mirror(power=65535)
        mirror.state.power = 0  # connected while off, turned on in the app

        await mirror.turn_front_on(self.AMBER)

        assert mirror.state.power == 65535
        assert mirror.state.front_is_on is True

    async def test_apply_theme_power_on_trusts_a_fading_power_off(self) -> None:
        """Test that apply_theme(power_on=True) powers on after a power-off.

        GetPower still reports on while the power-off fades, which would make
        MatrixLight.apply_theme() skip the power-on.
        """
        mirror = _mirror(power=65535)
        mirror.set_power = AsyncMock()
        mirror._record_power(False, 1.0)

        with patch(
            "lifx.devices.matrix.MatrixLight.apply_theme", new_callable=AsyncMock
        ) as matrix_theme:
            await mirror.apply_theme(Theme([self.AMBER]), power_on=True, duration=1.0)

        assert matrix_theme.await_args.kwargs["power_on"] is False
        # The power-off is still fading, so the theme fades in too
        assert matrix_theme.await_args.kwargs["duration"] == 1.0
        mirror.set_power.assert_awaited_once_with(True, 1.0)

    async def test_last_component_off_powers_the_device_off(self) -> None:
        """Test that turning off the only lit component powers the light down.

        The front keeps its brightness on the device, so a later
        set_power(True) brings it back instead of a light showing nothing.
        """
        mirror = _mirror()
        dark = HSBK(hue=30, saturation=0.4, brightness=0.0, kelvin=2700)
        buffer = _buffer([self.LIT] * 25, [dark] * 25)
        mirror.get_all_tile_colors = AsyncMock(return_value=[buffer])

        with patch(
            "lifx.devices.light.Light.set_power", new_callable=AsyncMock
        ) as light_power:
            await mirror.turn_front_off(duration=2.0)

        light_power.assert_awaited_once_with(False, 2.0)
        mirror.set_matrix_colors.assert_not_awaited()
        assert mirror.state.front_is_on is False
        assert mirror.state.back_is_on is False
        assert mirror.state.stored_front_colors == [self.LIT] * 25

    async def test_back_off_with_front_dark_powers_the_device_off(self) -> None:
        """Test the power-off path when the back is the last lit component."""
        mirror = _mirror()
        dark = HSBK(hue=30, saturation=0.4, brightness=0.0, kelvin=2700)
        buffer = _buffer([dark] * 25, [self.LIT] * 25)
        mirror.get_all_tile_colors = AsyncMock(return_value=[buffer])

        with patch(
            "lifx.devices.light.Light.set_power", new_callable=AsyncMock
        ) as light_power:
            await mirror.turn_back_off(duration=2.0)

        light_power.assert_awaited_once_with(False, 2.0)
        mirror.set_matrix_colors.assert_not_awaited()
        assert mirror.state.front_is_on is False
        assert mirror.state.back_is_on is False
        assert mirror.state.stored_back_colors == [self.LIT] * 25

    async def test_last_component_off_writes_supplied_hsk_after_power_off(
        self,
    ) -> None:
        """Test that caller colours reach the device, keeping its brightness."""
        mirror = _mirror()
        dark = HSBK(hue=30, saturation=0.4, brightness=0.0, kelvin=2700)
        buffer = _buffer([self.LIT] * 25, [dark] * 25)
        mirror.get_all_tile_colors = AsyncMock(return_value=[buffer])
        stored = HSBK(hue=200, saturation=0.5, brightness=0.6, kelvin=4000)

        with patch("lifx.devices.light.Light.set_power", new_callable=AsyncMock):
            await mirror.turn_front_off(stored)

        written = mirror.set_matrix_colors.call_args.args[1]
        assert mirror.set_matrix_colors.call_args.kwargs["duration"] == 0
        assert all(
            c.hue == 200 and c.kelvin == 4000 and c.brightness == self.LIT.brightness
            for c in _front_of(written)
        )
        assert mirror.state.stored_front_colors == [stored] * 25

    async def test_last_component_off_during_fade_only_stores_colors(
        self,
    ) -> None:
        """Test that new H/S/K is not written while the power-off is visible."""
        mirror = _mirror()
        dark = HSBK(hue=30, saturation=0.4, brightness=0.0, kelvin=2700)
        buffer = _buffer([self.LIT] * 25, [dark] * 25)
        mirror.get_all_tile_colors = AsyncMock(return_value=[buffer])
        stored = HSBK(hue=200, saturation=0.5, brightness=0.6, kelvin=4000)

        with patch("lifx.devices.light.Light.set_power", new_callable=AsyncMock):
            await mirror.turn_front_off(stored, duration=3.0)

        mirror.set_matrix_colors.assert_not_awaited()
        assert mirror.state.stored_front_colors == [stored] * 25

    async def test_dark_component_keeps_its_stored_colors(self) -> None:
        """Test that a dark component's stored colours are not replaced by zeros.

        Neither turning the other component on from power-off nor turning the
        dark component off again may overwrite them.
        """
        mirror = _mirror(power=0)
        dark = HSBK(hue=30, saturation=0.4, brightness=0.0, kelvin=2700)
        stored_back = [HSBK(hue=200, saturation=0.5, brightness=0.2, kelvin=4000)] * 25
        mirror.state.stored_back_colors = list(stored_back)
        buffer = _buffer([self.LIT] * 25, [dark] * 25)
        mirror.get_all_tile_colors = AsyncMock(return_value=[buffer])

        with patch("lifx.devices.light.Light.set_power", new_callable=AsyncMock):
            await mirror.turn_front_on(self.AMBER)
            await mirror.turn_back_off()

        assert mirror.state.stored_back_colors == stored_back

    async def test_turn_on_right_after_power_off_powers_back_on(self) -> None:
        """Test that a stale GetPower does not skip powering the light back on.

        GetPower still reports the old level just after a SetPower, so the
        turn-on must trust the power-off it has just sent.
        """
        mirror = _mirror(power=65535)
        dark = HSBK(hue=30, saturation=0.4, brightness=0.0, kelvin=2700)
        buffer = _buffer([self.LIT] * 25, [dark] * 25)
        mirror.get_all_tile_colors = AsyncMock(return_value=[buffer])

        with patch(
            "lifx.devices.light.Light.set_power", new_callable=AsyncMock
        ) as light_power:
            await mirror.turn_front_off(duration=1.0)
            await mirror.turn_back_on(self.AMBER, duration=1.0)

        assert light_power.await_args_list == [call(False, 1.0), call(True, 1.0)]
        written = mirror.set_matrix_colors.call_args.args[1]
        assert _back_of(written) == [self.AMBER] * 25
        assert all(c.brightness == 0 for c in _front_of(written))
        # The power-off is still fading out, so the light is visibly lit and
        # the zones fade too rather than snapping
        assert mirror.set_matrix_colors.call_args.kwargs["duration"] == 1000

    async def test_turn_on_after_power_off_finished_preloads_instantly(
        self,
    ) -> None:
        """Test that the zones are loaded instantly once the light is dark."""
        mirror = _mirror(power=65535)
        dark = HSBK(hue=30, saturation=0.4, brightness=0.0, kelvin=2700)
        buffer = _buffer([self.LIT] * 25, [dark] * 25)
        mirror.get_all_tile_colors = AsyncMock(return_value=[buffer])

        with (
            patch("lifx.devices.light.Light.set_power", new_callable=AsyncMock),
            patch(
                "lifx.devices.component_state.time.monotonic", return_value=100.0
            ) as clock,
        ):
            await mirror.turn_front_off(duration=1.0)
            # Fade finished, but still inside the settle margin, so the
            # stale GetPower is still not trusted
            clock.return_value = 101.2
            await mirror.turn_back_on(self.AMBER, duration=1.0)

        assert mirror.set_matrix_colors.call_args.kwargs["duration"] == 0


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
        """Test that power_on writes colours first, then fades the light up.

        The front keeps its brightness after a last-component power-off, so it
        must be zeroed or it would come back on with the back.
        """
        mirror = _mirror(power=0)
        theme = Theme([HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=3500)])

        with patch(
            "lifx.devices.light.Light.set_power", new_callable=AsyncMock
        ) as light_power:
            await mirror.apply_back_theme(theme, power_on=True, duration=3.0)

        assert mirror.set_matrix_colors.call_args.kwargs["duration"] == 0
        written = mirror.set_matrix_colors.call_args.args[1]
        assert all(c.brightness == 0 for c in _front_of(written))
        assert all(c.brightness > 0 for c in _back_of(written))
        light_power.assert_awaited_once_with(True, 3.0)

    async def test_set_color_before_entering_does_not_raise(self) -> None:
        """Test that set_color works on a Mirror straight from discover()."""
        mirror = _mirror()
        mirror._state = None

        with patch("lifx.devices.light.Light.set_color", new_callable=AsyncMock):
            await mirror.set_color(WHITE)

    async def test_brightness_that_rounds_to_zero_is_rejected(self) -> None:
        """Test that a brightness written as 0 on the wire counts as dark."""
        mirror = _mirror()

        with pytest.raises(ValueError, match="brightness=0"):
            await mirror.set_front_colors(
                HSBK(hue=30, saturation=0.5, brightness=5e-6, kelvin=2700)
            )

    def test_state_keeps_the_optional_light_fields(self) -> None:
        """Test that wifi, thread and ambient readings survive into the state."""
        matrix_state = MagicMock(power=65535)

        state = MirrorLightState.from_matrix_state(
            matrix_state, [WHITE] * 25, [WHITE] * 25, FRONT_POSITIONS, BACK_POSITIONS
        )

        assert state.wifi_info is matrix_state.wifi_info
        assert state.thread_info is matrix_state.thread_info
        assert state.ambient_light is matrix_state.ambient_light


class TestMirrorStatePersistence:
    """Tests for the JSON state file."""

    async def test_save_and_load_round_trip(self) -> None:
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

            await saver._save_state_to_file()

            document = json.loads(Path(state_file).read_text())
            assert len(document["d073d5010203"]["front"]) == 25
            assert len(document["d073d5010203"]["back"]) == 25

            loader = _mirror()
            loader._state_file = state_file
            loader._state.stored_front_colors = None
            loader._state.stored_back_colors = None

            await loader._load_state_from_file()

            assert loader._state.stored_front_colors == front
            assert loader._state.stored_back_colors == back

    async def test_load_ignores_wrong_zone_count(self) -> None:
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

            await mirror._load_state_from_file()

            assert mirror._state.stored_front_colors is None

    async def test_load_missing_file_is_quiet(self) -> None:
        """Test that a missing state file leaves stored colours untouched."""
        mirror = _mirror()
        mirror._state_file = "/nonexistent/path/mirror.json"
        mirror._state.stored_front_colors = None

        await mirror._load_state_from_file()

        assert mirror._state.stored_front_colors is None


class TestMirrorZoneMapValidation:
    """Tests for zone map to buffer position derivation."""

    def test_missing_zone_is_rejected(self) -> None:
        """Test that a zone map with a gap is reported, not silently accepted."""
        with pytest.raises(ValueError, match="Zone 2 is missing from the zone map"):
            _buffer_positions((0, 1, -1), range(0, 3))
