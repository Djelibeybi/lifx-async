"""A Ceiling's Animator composes one slot per light component into one tile."""

from __future__ import annotations

import struct
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lifx.animation.packets import HEADER_SIZE
from lifx.color import HSBK
from lifx.devices.ceiling import CeilingLight
from lifx.devices.component.effect_support import component_writer
from lifx.products import get_product
from lifx.protocol import packets
from lifx.protocol.protocol_types import LightHsbk
from tests.test_animation.conftest import MockUdpSocket, make_ack_datagram
from tests.test_devices.test_component_transitions import Rig, build_rig

_SET64_COLOURS = HEADER_SIZE + 10

GREEN = HSBK.from_protocol(HSBK(120, 1, 1, 3500).to_protocol())
DIM_BLUE = HSBK.from_protocol(HSBK(240, 1, 0.3, 3500).to_protocol())
AMBER = HSBK.from_protocol(HSBK(40, 0.8, 0.6, 2700).to_protocol())
RED = (0, 65535, 65535, 3500)
CYAN = (32768, 65535, 65535, 3500)

UPLIGHT = 63  # the 8x8 Ceiling's last cell


def _ceiling() -> CeilingLight:
    """An 8x8 Ceiling: green downlight, dim blue uplight, one Set64 per frame."""
    ceiling = CeilingLight(serial="d073d5000176", ip="192.0.2.13")
    ceiling._version = MagicMock(product=176)
    ceiling._capabilities = get_product(176)
    tile = MagicMock(width=8, height=8, user_x=0.0, user_y=0.0)
    tile.nearest_orientation = "Upright"
    ceiling._device_chain = [tile]
    ceiling.get_all_tile_colors = AsyncMock(
        side_effect=lambda: [[GREEN] * UPLIGHT + [DIM_BLUE]]
    )
    ceiling.set_matrix_colors = AsyncMock()
    return ceiling


@pytest.fixture
def rig(monkeypatch: pytest.MonkeyPatch) -> Rig:
    """An 8x8 Ceiling with state, on an in-memory tile peer."""
    rig = build_rig(176, monkeypatch)
    rig.wire.colours[:] = [GREEN] * UPLIGHT + [DIM_BLUE]
    rig.light._capabilities = get_product(176)
    return rig


def _tile_writes(rig: Rig) -> list[packets.Packet]:
    return [p for p in rig.wire.packets if isinstance(p, packets.Tile.Set64)]


def _tile_reads(rig: Rig) -> list[packets.Packet]:
    return [p for p in rig.wire.packets if isinstance(p, packets.Tile.Get64)]


@pytest.fixture
def sent(mock_udp_socket: MockUdpSocket) -> list[bytes]:
    """Copies of every datagram, taken as sent: templates are reused."""
    datagrams: list[bytes] = []
    mock_udp_socket.sock.sendto.side_effect = lambda data, _addr: datagrams.append(
        bytes(data)
    )
    return datagrams


def _tiles(sent: list[bytes]) -> list[list[tuple[int, ...]]]:
    tiles = []
    for data in sent:
        flat = struct.unpack_from("<256H", data, _SET64_COLOURS)
        tiles.append([flat[i : i + 4] for i in range(0, 256, 4)])
    return tiles


def _frame(count: int) -> list[tuple[int, int, int, int]]:
    """A frame no single colour can reproduce."""
    return [((i * 997) % 65536, 65535, 40000, 3500) for i in range(count)]


class TestComponentSlots:
    async def test_a_downlight_frame_drops_the_uplight_cell(
        self, sent: list[bytes]
    ) -> None:
        ceiling = _ceiling()
        writer = await component_writer(ceiling, "downlight", 0)
        frame = _frame(64)

        writer.send_frame(frame)

        (tile,) = _tiles(sent)
        assert (writer.pixel_count, writer.canvas_width, writer.canvas_height) == (
            64,
            8,
            8,
        )
        assert tile[:UPLIGHT] == frame[:UPLIGHT]
        assert tile[UPLIGHT] == DIM_BLUE.as_tuple()

    async def test_an_uplight_frame_is_one_pixel_beside_the_held_downlight(
        self, sent: list[bytes]
    ) -> None:
        ceiling = _ceiling()
        writer = await component_writer(ceiling, "uplight", 0)

        writer.send_frame([RED])

        (tile,) = _tiles(sent)
        assert writer.pixel_count == 1
        assert tile[UPLIGHT] == RED
        assert tile[:UPLIGHT] == [GREEN.as_tuple()] * UPLIGHT

    async def test_two_component_slots_compose_into_one_tile(
        self, sent: list[bytes]
    ) -> None:
        ceiling = _ceiling()
        downlight = await component_writer(ceiling, "downlight", 0)
        uplight = await component_writer(ceiling, "uplight", 0)
        frame = _frame(64)

        downlight.send_frame(frame)
        uplight.send_frame([RED])

        assert _tiles(sent)[-1] == frame[:UPLIGHT] + [RED]
        assert ceiling.get_all_tile_colors.await_count == 1

    async def test_an_idle_component_change_rides_on_the_next_frame(
        self, sent: list[bytes], rig: Rig
    ) -> None:
        ceiling = rig.light
        assert isinstance(ceiling, CeilingLight)
        writer = await component_writer(ceiling, "downlight", 0)
        frame = _frame(64)

        await ceiling.set_uplight_color(AMBER)
        writer.send_frame(frame)

        assert _tile_writes(rig) == []
        assert _tiles(sent)[-1][UPLIGHT] == AMBER.as_tuple()
        assert ceiling.state.stored_uplight_color == AMBER
        assert ceiling.state.uplight_color == AMBER

    async def test_an_idle_component_fades_on_the_host(
        self, sent: list[bytes], rig: Rig
    ) -> None:
        ceiling = rig.light
        assert isinstance(ceiling, CeilingLight)
        writer = await component_writer(ceiling, "downlight", 0)
        frame = _frame(64)

        with patch("lifx.animation.slots.time.monotonic", return_value=100.0):
            await ceiling.set_uplight_color(AMBER, duration=2.0)
        for now in (101.0, 103.0):
            with patch("lifx.animation.animator.time.monotonic", return_value=now):
                writer.send_frame(frame)

        halfway, done = (tile[UPLIGHT] for tile in _tiles(sent))
        expected = DIM_BLUE.lerp_hsb(AMBER, 0.5).with_kelvin(3100)
        assert halfway == expected.as_tuple()
        assert done == AMBER.as_tuple()

    async def test_releasing_a_slot_keeps_the_other_components_fade(
        self, sent: list[bytes], rig: Rig
    ) -> None:
        """Only the released light component's cells change when it lets go."""
        ceiling = rig.light
        assert isinstance(ceiling, CeilingLight)
        writer = await component_writer(ceiling, "downlight", 0)
        frame = _frame(64)

        with patch("lifx.animation.slots.time.monotonic", return_value=100.0):
            await ceiling.set_uplight_color(AMBER, duration=2.0)
        with patch("lifx.animation.animator.time.monotonic", return_value=100.5):
            writer.send_frame(frame)
        with patch("lifx.animation.slots.time.monotonic", return_value=101.0):
            writer.close()

        hold = ceiling.animator._hold
        assert hold is not None
        halfway = DIM_BLUE.lerp_hsb(AMBER, 0.5).with_kelvin(3100)
        assert hold.tuples_at(101.0)[UPLIGHT] == halfway.as_tuple()
        assert hold.tuples_at(103.0)[UPLIGHT] == AMBER.as_tuple()
        assert hold.tuples_at(101.0)[0] == _tiles(sent)[-1][0]

    async def test_a_released_writer_draws_nothing(self, sent: list[bytes]) -> None:
        ceiling = _ceiling()
        writer = await component_writer(ceiling, "uplight", 0)
        writer.close()
        writer.close()

        stats = writer.send_frame([RED])

        assert stats.packets_sent == 0
        assert sent == []
        with pytest.raises(ValueError, match="pixel_count"):
            writer.send_frame([RED, RED])

    async def test_a_slot_keeps_its_frame_while_another_writer_draws_on_it(
        self, sent: list[bytes], mock_udp_socket: MockUdpSocket
    ) -> None:
        """Releasing the last writer leaves its last frame showing.

        The light component's frame becomes part of the held tile, so the
        other light component's next frame does not snap it back to the
        colours from before the effect; a restore or a caller's write does.
        """
        ceiling = _ceiling()
        first = await component_writer(ceiling, "uplight", 0)
        second = await component_writer(ceiling, "uplight", 0)
        downlight = await component_writer(ceiling, "downlight", 0)
        frame = _frame(64)
        second.send_frame([CYAN])

        first.close()
        downlight.send_frame(frame)
        mock_udp_socket.queue_datagram(make_ack_datagram(ceiling.animator._source, 0))
        second.close()
        downlight.send_frame(frame)

        before, after = _tiles(sent)[-2:]
        assert before[UPLIGHT] == CYAN
        assert after[UPLIGHT] == CYAN
        assert ceiling.animator._held_tile()[UPLIGHT] == HSBK.from_protocol(
            LightHsbk(*CYAN)
        )

    async def test_the_held_tile_outlives_the_effect_until_the_tile_is_rewritten(
        self, sent: list[bytes], rig: Rig
    ) -> None:
        ceiling = rig.light
        assert isinstance(ceiling, CeilingLight)
        writer = await component_writer(ceiling, "downlight", 0)
        await ceiling.set_uplight_color(AMBER)
        writer.close()
        reads = len(_tile_reads(rig))

        await ceiling.set_downlight_colors(DIM_BLUE)

        assert len(_tile_reads(rig)) == reads
        assert rig.wire.colours == [DIM_BLUE] * UPLIGHT + [AMBER]

    async def test_a_whole_tile_frame_forgets_the_held_tile(
        self, sent: list[bytes], rig: Rig
    ) -> None:
        ceiling = rig.light
        assert isinstance(ceiling, CeilingLight)
        writer = await component_writer(ceiling, "downlight", 0)
        await ceiling.set_uplight_color(AMBER)
        writer.close()
        reads = len(_tile_reads(rig))

        ceiling.animator.send_frame(_frame(64))
        await ceiling.set_downlight_colors(AMBER)

        assert len(_tile_reads(rig)) > reads
        assert rig.wire.colours == [AMBER] * UPLIGHT + [DIM_BLUE]

    async def test_a_whole_tile_frame_during_a_component_effect_keeps_the_hold(
        self, sent: list[bytes], mock_udp_socket: MockUdpSocket
    ) -> None:
        ceiling = _ceiling()
        writer = await component_writer(ceiling, "downlight", 0)
        raw = _frame(64)

        ceiling.animator.send_frame(raw)
        mock_udp_socket.queue_datagram(make_ack_datagram(ceiling.animator._source, 0))
        writer.send_frame(raw[::-1])

        whole, composed = _tiles(sent)
        assert whole == raw
        assert composed[UPLIGHT] == DIM_BLUE.as_tuple()

    async def test_a_slot_frame_can_carry_its_own_duration(
        self, sent: list[bytes]
    ) -> None:
        ceiling = _ceiling()
        writer = await component_writer(ceiling, "uplight", 75)

        writer.send_frame([RED], duration_ms=3000)

        assert writer.draws_slot is True
        (datagram,) = sent
        assert struct.unpack_from("<I", datagram, HEADER_SIZE + 6) == (3000,)

    async def test_a_tile_is_shared_while_another_effect_draws_on_it(self) -> None:
        ceiling = _ceiling()
        uplight = await component_writer(ceiling, "uplight", 0)

        assert uplight.tile_shared([uplight]) is False

        downlight = await component_writer(ceiling, "downlight", 0)

        assert uplight.tile_shared([uplight]) is True
        assert uplight.tile_shared([uplight, downlight]) is False
        downlight.close()
        assert uplight.tile_shared([uplight]) is False

    async def test_a_writer_sees_a_held_fade_and_its_time_left(self, rig: Rig) -> None:
        ceiling = rig.light
        assert isinstance(ceiling, CeilingLight)
        writer = await component_writer(ceiling, "uplight", 0)
        before = writer.hold_version

        with patch("lifx.animation.slots.time.monotonic", return_value=100.0):
            await ceiling.set_downlight_colors(AMBER, duration=2.0)

        assert writer.hold_version != before
        with patch("lifx.animation.animator.time.monotonic", return_value=101.5):
            assert writer.hold_remaining == pytest.approx(0.5)
        with patch("lifx.animation.animator.time.monotonic", return_value=102.5):
            assert writer.hold_remaining == 0.0

    async def test_a_settled_frame_carries_the_held_fades_final_colours(
        self, sent: list[bytes], rig: Rig
    ) -> None:
        ceiling = rig.light
        assert isinstance(ceiling, CeilingLight)
        writer = await component_writer(ceiling, "uplight", 0)
        with patch("lifx.animation.slots.time.monotonic", return_value=100.0):
            await ceiling.set_downlight_colors(AMBER, duration=2.0)

        with patch("lifx.animation.animator.time.monotonic", return_value=101.0):
            writer.send_frame([RED], duration_ms=1000, settled=True)

        (tile,) = _tiles(sent)
        assert tile[:UPLIGHT] == [AMBER.as_tuple()] * UPLIGHT
        assert tile[UPLIGHT] == RED

    async def test_a_tile_with_nothing_held_has_version_zero(self) -> None:
        animator = await _ceiling().animator.prepare()

        assert animator._writer().hold_version == 0

    def test_reading_the_components_changes_nothing(self) -> None:
        ceiling = _ceiling()

        assert ceiling.uplight is ceiling.uplight
        assert ceiling.downlight.animator is ceiling.animator
        assert repr(ceiling.downlight) == (
            "LightComponent('downlight', serial='d073d5000176')"
        )
        assert ceiling._animating_components() == frozenset()
