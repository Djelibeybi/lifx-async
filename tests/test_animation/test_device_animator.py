"""Every light owns one Animator, borrowed by direct users and the Conductor."""

from __future__ import annotations

import asyncio
import inspect
import struct
from unittest.mock import AsyncMock, MagicMock

import pytest

from lifx.animation.animator import Animator
from lifx.animation.packets import HEADER_SIZE
from lifx.devices.light import Light
from lifx.devices.matrix import MatrixLight
from lifx.devices.mirror import MirrorLight
from lifx.devices.multizone import MultiZoneLight
from lifx.products import get_product
from tests.test_animation.conftest import MockUdpSocket, make_ack_datagram

# Set64: header, then tile index, length, rect (4) and duration (4) before
# the colours.
_SET64_DURATION = HEADER_SIZE + 6
_SET64_COLOURS = HEADER_SIZE + 10


def _matrix(width: int = 8, height: int = 8) -> MatrixLight:
    device = MatrixLight(serial="d073d5000007", ip="192.0.2.10")
    tile = MagicMock(width=width, height=height, user_x=0.0, user_y=0.0)
    tile.nearest_orientation = "Upright"

    async def load_chain() -> list[MagicMock]:
        device._device_chain = [tile]
        return [tile]

    device.get_device_chain = AsyncMock(side_effect=load_chain)
    device._capabilities = MagicMock(has_chain=False)
    return device


def _mirror() -> MirrorLight:
    device = MirrorLight(serial="d073d5000267", ip="192.0.2.11")
    device._version = MagicMock(product=267)
    device._capabilities = get_product(267)
    tile = MagicMock(width=4, height=13, user_x=0.0, user_y=0.0)
    tile.nearest_orientation = "Upright"
    device._device_chain = [tile]
    return device


def _strip(extended: bool = True) -> MultiZoneLight:
    device = MultiZoneLight(serial="d073d5000005", ip="192.0.2.12")
    device._capabilities = MagicMock(has_extended_multizone=extended)
    device.get_zone_count = AsyncMock(return_value=16)
    return device


def _set64_tiles(udp: MockUdpSocket) -> list[list[tuple[int, ...]]]:
    tiles = []
    for call in udp.sock.sendto.call_args_list:
        data = bytes(call.args[0])
        flat = struct.unpack_from("<256H", data, _SET64_COLOURS)
        tiles.append([flat[i : i + 4] for i in range(0, 256, 4)])
    return tiles


def _durations(udp: MockUdpSocket) -> list[int]:
    return [
        struct.unpack_from("<I", bytes(call.args[0]), _SET64_DURATION)[0]
        for call in udp.sock.sendto.call_args_list
    ]


class TestDeviceAnimator:
    def test_a_light_returns_the_same_animator_on_every_access(self) -> None:
        light = Light(serial="d073d5000001", ip="192.0.2.10")

        assert light.animator is light.animator

    def test_a_single_light_animator_is_ready_without_preparing(
        self, mock_udp_socket: MockUdpSocket
    ) -> None:
        light = Light(serial="d073d5000001", ip="192.0.2.10")

        stats = light.animator.send_frame([(0, 0, 65535, 3500)])

        assert light.animator.pixel_count == 1
        assert stats.packets_sent == 1

    def test_a_matrix_animator_must_be_prepared_before_drawing(self) -> None:
        device = _matrix()

        with pytest.raises(RuntimeError, match="prepare"):
            device.animator.send_frame([(0, 0, 0, 3500)] * 64)
        with pytest.raises(RuntimeError, match="prepare"):
            _ = device.animator.pixel_count

    async def test_preparing_queries_the_geometry_once(self) -> None:
        device = _matrix()

        animator = await device.animator.prepare()
        again = await device.animator.prepare()

        assert animator is again is device.animator
        assert (animator.canvas_width, animator.canvas_height) == (8, 8)
        assert animator.wraps is False
        device.get_device_chain.assert_awaited_once()

    async def test_concurrent_prepares_keep_the_first_geometry(
        self, mock_udp_socket: MockUdpSocket
    ) -> None:
        device = _matrix()
        load = device.get_device_chain.side_effect

        async def slow_load() -> list[MagicMock]:
            await asyncio.sleep(0)
            return await load()

        device.get_device_chain.side_effect = slow_load

        first, second = await asyncio.gather(
            device.animator.prepare(), device.animator.prepare()
        )
        geometry = device.animator._require_geometry()
        await device.animator.prepare()

        assert first is second is device.animator
        assert device.animator._require_geometry() is geometry
        assert device.get_device_chain.await_count == 2
        assert first.send_frame([(0, 0, 0, 3500)] * 64).packets_sent == 1

    async def test_every_prepare_tells_the_device_its_zones_change(self) -> None:
        """Frames bypass set64(), so a component light forgets its tile."""
        device = _mirror()
        await device.animator.prepare()
        device._pending_tile.record([MagicMock()] * 52, 5.0)

        await device.animator.prepare()

        assert device._pending_tile.get() is None

    async def test_a_mirror_animator_keeps_the_raw_tile_canvas(self) -> None:
        """LedFx and other direct users still get the 52-position tile."""
        animator = await _mirror().animator.prepare()

        assert animator.pixel_count == 52
        assert animator.wraps is False

    async def test_a_matrix_without_tiles_cannot_be_prepared(self) -> None:
        device = _matrix()
        device._device_chain = []

        with pytest.raises(ValueError, match="no tiles"):
            await device.animator.prepare()

    async def test_a_strip_animator_draws_on_its_zones(self) -> None:
        animator = await _strip().animator.prepare()

        assert (animator.pixel_count, animator.canvas_height) == (16, 1)

    async def test_a_strip_loads_its_capabilities_before_preparing(self) -> None:
        device = _strip()
        device._capabilities = None

        async def load() -> None:
            device._capabilities = MagicMock(has_extended_multizone=True)

        device.ensure_capabilities = AsyncMock(side_effect=load)

        await device.animator.prepare()

        device.ensure_capabilities.assert_awaited_once()

    async def test_a_strip_without_extended_multizone_cannot_animate(self) -> None:
        with pytest.raises(ValueError, match="extended multizone"):
            await _strip(extended=False).animator.prepare()

    async def test_a_directly_built_animator_is_already_prepared(self) -> None:
        light = Light(serial="d073d5000001", ip="192.0.2.10")
        with pytest.warns(DeprecationWarning):
            borrowed = Animator.for_light(light)
        direct = Animator(
            "192.0.2.10",
            borrowed._serial,
            borrowed._require_geometry().framebuffer,
            borrowed._require_geometry().packet_generator,
        )

        assert await direct.prepare() is direct

    def test_duration_cannot_be_negative(self) -> None:
        light = Light(serial="d073d5000001", ip="192.0.2.10")

        with pytest.raises(ValueError, match="non-negative"):
            light.animator.duration_ms = -1


class TestDeprecatedFactories:
    async def test_for_matrix_returns_the_device_animator(self) -> None:
        device = _matrix()

        with pytest.warns(DeprecationWarning, match=r"device\.animator"):
            first = await Animator.for_matrix(device, duration_ms=40)
        with pytest.warns(DeprecationWarning, match=r"device\.animator"):
            second = await Animator.for_matrix(device)

        assert first is second is device.animator
        assert first.pixel_count == 64

    async def test_for_multizone_returns_the_device_animator(self) -> None:
        device = _strip()

        with pytest.warns(DeprecationWarning, match=r"device\.animator"):
            first = await Animator.for_multizone(device)
        with pytest.warns(DeprecationWarning, match=r"device\.animator"):
            second = await Animator.for_multizone(device)

        assert first is second is device.animator

    def test_for_light_returns_the_device_animator(self) -> None:
        light = Light(serial="d073d5000001", ip="192.0.2.10")

        with pytest.warns(DeprecationWarning, match=r"device\.animator"):
            first = Animator.for_light(light, duration_ms=500)
        with pytest.warns(DeprecationWarning, match=r"device\.animator"):
            second = Animator.for_light(light, duration_ms=500)

        assert first is second is light.animator
        assert first.duration_ms == 500

    def test_the_factories_keep_their_signatures(self) -> None:
        # The positional parameters are unchanged; the Thread opt-in is
        # keyword-only and off by default, so existing calls still bind.
        for factory in (Animator.for_matrix, Animator.for_multizone):
            assert inspect.iscoroutinefunction(factory)
        assert not inspect.iscoroutinefunction(Animator.for_light)
        for factory in (
            Animator.for_matrix,
            Animator.for_multizone,
            Animator.for_light,
        ):
            parameters = inspect.signature(factory).parameters
            assert list(parameters) == ["device", "duration_ms", "enable_thread"]
            opt_in = parameters["enable_thread"]
            assert opt_in.kind is inspect.Parameter.KEYWORD_ONLY
            assert opt_in.default is False

    def test_the_warning_points_at_the_caller(self) -> None:
        light = Light(serial="d073d5000001", ip="192.0.2.10")

        with pytest.warns(DeprecationWarning) as record:
            Animator.for_light(light)

        assert record[0].filename == __file__

    def test_for_light_cannot_prepare_a_matrix(self) -> None:
        with (
            pytest.warns(DeprecationWarning),
            pytest.raises(RuntimeError, match="prepare"),
        ):
            Animator.for_light(_matrix())

    async def test_the_factory_duration_reaches_the_wire(
        self, mock_udp_socket: MockUdpSocket
    ) -> None:
        device = _matrix()
        with pytest.warns(DeprecationWarning):
            animator = await Animator.for_matrix(device, duration_ms=40)

        animator.send_frame([(0, 0, 0, 3500)] * 64)

        assert _durations(mock_udp_socket) == [40]


class TestWriters:
    async def test_each_writer_sends_at_its_own_duration(
        self, mock_udp_socket: MockUdpSocket
    ) -> None:
        animator = await _matrix().animator.prepare()
        animator.duration_ms = 0
        writer = animator._writer(duration_ms=50)
        frame = [(0, 0, 0, 3500)] * 64

        writer.send_frame(frame)
        animator.send_frame(frame)
        mock_udp_socket.queue_datagram(make_ack_datagram(animator._source, 0))
        writer.send_frame(frame)

        assert writer.pixel_count == 64
        assert writer.wraps is False
        assert _durations(mock_udp_socket) == [50, 0, 50]

    async def test_closing_a_writer_leaves_the_animator_open(
        self, mock_udp_socket: MockUdpSocket
    ) -> None:
        animator = await _matrix().animator.prepare()
        writer = animator._writer()
        writer.send_frame([(0, 0, 0, 3500)] * 64)

        writer.close()

        mock_udp_socket.sock.close.assert_not_called()

    async def test_a_direct_caller_and_a_writer_share_one_ack_gate(
        self, mock_udp_socket: MockUdpSocket
    ) -> None:
        """Two writers on one light never get two gates' worth of traffic."""
        device = _matrix()
        with pytest.warns(DeprecationWarning):
            ledfx = await Animator.for_matrix(device)
        writer = device.animator._writer(duration_ms=50)
        frame = [(0, 0, 0, 3500)] * 64

        first = ledfx.send_frame(frame)
        second = writer.send_frame(frame)
        third = ledfx.send_frame(frame)

        assert not first.gated and not second.gated
        assert third.gated
        assert mock_udp_socket.socket_class.call_count == 1

        # An ack for the writer's probe reopens the gate for the direct caller.
        mock_udp_socket.queue_datagram(make_ack_datagram(ledfx._source, 1))
        assert not ledfx.send_frame(frame).gated

    def test_a_writer_needs_a_prepared_animator(self) -> None:
        with pytest.raises(RuntimeError, match="prepare"):
            _matrix().animator._writer()


async def test_a_single_light_describes_its_own_geometry() -> None:
    """A single light answers a geometry query without asking the device."""
    light = Light(serial="d073d5000001", ip="192.0.2.13")

    framebuffer, generator = await light._query_animation_geometry()

    assert framebuffer.canvas_size == 1
    assert generator.pixel_count() == 1
