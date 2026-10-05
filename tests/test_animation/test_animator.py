"""Tests for the high-level Animator class."""

from __future__ import annotations

import asyncio
import inspect
import socket
import time
from unittest.mock import MagicMock, patch

import pytest

import lifx.animation
from lifx.animation.animator import Animator, AnimatorStats
from lifx.animation.framebuffer import FrameBuffer
from lifx.animation.packets import MatrixPacketGenerator
from lifx.devices.light import Light
from lifx.devices.matrix import MatrixLight
from lifx.devices.multizone import MultiZoneLight
from lifx.exceptions import LifxNetworkError
from lifx.protocol.models import Serial
from tests.test_animation.conftest import MockUdpSocket, make_ack_datagram


async def _drain_probe_acks(animator: Animator, timeout: float = 2.0) -> None:
    """Wait until every outstanding probe ack has arrived and been swept.

    A fixed sleep assumes the emulator answers within that window, which a
    loaded CI runner does not guarantee. Sweeping until the gate is empty,
    bounded by ``timeout``, waits exactly as long as the reply takes.
    """
    deadline = time.monotonic() + timeout
    while animator._ack_gate.outstanding_count:
        if time.monotonic() > deadline:
            raise AssertionError("probe ack did not arrive within the timeout")
        await asyncio.sleep(0.01)
        assert animator._socket is not None
        animator._ack_gate.sweep(animator._socket, animator._source, time.monotonic())


class TestAnimatorStats:
    """Tests for AnimatorStats dataclass."""

    def test_stats_fields(self) -> None:
        """Test AnimatorStats has correct fields."""
        stats = AnimatorStats(
            packets_sent=5,
            total_time_ms=10.5,
        )
        assert stats.packets_sent == 5
        assert stats.total_time_ms == 10.5

    def test_frozen_dataclass(self) -> None:
        """Verify AnimatorStats is immutable."""
        stats = AnimatorStats(packets_sent=5, total_time_ms=10.5)
        with pytest.raises(AttributeError):
            stats.packets_sent = 10  # type: ignore[misc]


class TestAnimatorConstruction:
    """Tests for Animator construction and properties."""

    def test_init_with_components(self) -> None:
        """Test direct constructor works."""
        framebuffer = FrameBuffer(pixel_count=64)
        packet_generator = MatrixPacketGenerator(
            tile_count=1, tile_width=8, tile_height=8
        )
        serial = Serial.from_string("d073d5123456")

        animator = Animator(
            ip="192.168.1.100",
            serial=serial,
            framebuffer=framebuffer,
            packet_generator=packet_generator,
        )

        assert animator.pixel_count == 64

    def test_invalid_ip_fails_during_construction(self) -> None:
        """Permanent address errors do not surface inside the render loop."""
        with pytest.raises(ValueError, match="Invalid IP address format"):
            Animator(
                ip="not-an-ip",
                serial=Serial.from_string("d073d5123456"),
                framebuffer=FrameBuffer(pixel_count=64),
                packet_generator=MatrixPacketGenerator(
                    tile_count=1, tile_width=8, tile_height=8
                ),
            )

    def test_canvas_width_property(self) -> None:
        """Test canvas_width property delegation."""
        framebuffer = FrameBuffer(pixel_count=64, canvas_width=8, canvas_height=8)
        packet_generator = MatrixPacketGenerator(
            tile_count=1, tile_width=8, tile_height=8
        )
        serial = Serial.from_string("d073d5123456")

        animator = Animator(
            ip="192.168.1.100",
            serial=serial,
            framebuffer=framebuffer,
            packet_generator=packet_generator,
        )

        assert animator.canvas_width == 8
        assert animator.canvas_height == 8

    def test_pixel_count_from_framebuffer(self) -> None:
        """Test pixel_count property delegation."""
        framebuffer = FrameBuffer(pixel_count=128)
        packet_generator = MatrixPacketGenerator(
            tile_count=2, tile_width=8, tile_height=8
        )
        serial = Serial.from_string("d073d5123456")

        animator = Animator(
            ip="192.168.1.100",
            serial=serial,
            framebuffer=framebuffer,
            packet_generator=packet_generator,
        )

        assert animator.pixel_count == 128


class TestAnimatorSendFrame:
    """Tests for Animator.send_frame method."""

    @pytest.fixture
    def animator(self) -> Animator:
        """Create an animator for testing."""
        framebuffer = FrameBuffer(pixel_count=64)
        packet_generator = MatrixPacketGenerator(
            tile_count=1, tile_width=8, tile_height=8
        )
        serial = Serial.from_string("d073d5123456")

        return Animator(
            ip="192.168.1.100",
            serial=serial,
            framebuffer=framebuffer,
            packet_generator=packet_generator,
        )

    def test_send_frame_wrong_length_raises(self, animator: Animator) -> None:
        """Test that wrong Color array length raises ValueError."""
        hsbk: list[tuple[int, int, int, int]] = [
            (100, 100, 100, 3500)
        ] * 32  # Wrong length

        with pytest.raises(ValueError, match="must match pixel_count"):
            animator.send_frame(hsbk)

    def test_send_frame_sends_packets(
        self, animator: Animator, mock_udp_socket: MockUdpSocket
    ) -> None:
        """Test that send_frame sends packets via UDP."""
        hsbk: list[tuple[int, int, int, int]] = [(100, 100, 100, 3500)] * 64

        stats = animator.send_frame(hsbk)

        assert stats.packets_sent >= 1
        mock_udp_socket.sock.sendto.assert_called()

    def test_send_frame_returns_stats(
        self, animator: Animator, mock_udp_socket: MockUdpSocket
    ) -> None:
        """Test that send_frame returns AnimatorStats."""
        hsbk: list[tuple[int, int, int, int]] = [(100, 100, 100, 3500)] * 64

        stats = animator.send_frame(hsbk)

        assert isinstance(stats, AnimatorStats)
        assert stats.packets_sent >= 1
        assert stats.total_time_ms >= 0

    def test_send_frame_is_synchronous(self, animator: Animator) -> None:
        """Test that send_frame is synchronous (not a coroutine)."""
        assert not inspect.iscoroutinefunction(animator.send_frame)

    def test_send_frame_reuses_socket(
        self, animator: Animator, mock_udp_socket: MockUdpSocket
    ) -> None:
        """Test that send_frame reuses the same socket."""
        hsbk: list[tuple[int, int, int, int]] = [(100, 100, 100, 3500)] * 64

        # Send multiple frames
        animator.send_frame(hsbk)
        animator.send_frame(hsbk)
        animator.send_frame(hsbk)

        # Socket should only be created once
        assert mock_udp_socket.socket_class.call_count == 1

    def test_send_frame_sends_to_correct_address(
        self, animator: Animator, mock_udp_socket: MockUdpSocket
    ) -> None:
        """Test that packets are sent to correct IP:port."""
        hsbk: list[tuple[int, int, int, int]] = [(100, 100, 100, 3500)] * 64

        animator.send_frame(hsbk)

        # Check sendto was called with correct address
        call_args = mock_udp_socket.sock.sendto.call_args
        address = call_args[0][1]
        assert address == ("192.168.1.100", 56700)

    def test_send_frame_uses_ipv4_socket_family(
        self, animator: Animator, mock_udp_socket: MockUdpSocket
    ) -> None:
        """An IPv4 device address creates an AF_INET socket."""
        hsbk: list[tuple[int, int, int, int]] = [(100, 100, 100, 3500)] * 64

        animator.send_frame(hsbk)

        mock_udp_socket.socket_class.assert_called_once_with(
            socket.AF_INET, socket.SOCK_DGRAM
        )

    def test_send_frame_uses_ipv6_socket_family(
        self, mock_udp_socket: MockUdpSocket
    ) -> None:
        """A Thread device's IPv6 address creates an AF_INET6 socket.

        Thread devices have no IPv4 address, and an AF_INET socket raises
        gaierror when asked to send to an IPv6 one, so the socket family
        has to follow the device address.
        """
        animator = Animator(
            ip="fd00:1::",
            serial=Serial.from_string("d073d5123456"),
            framebuffer=FrameBuffer(pixel_count=64),
            packet_generator=MatrixPacketGenerator(
                tile_count=1, tile_width=8, tile_height=8
            ),
        )
        hsbk: list[tuple[int, int, int, int]] = [(100, 100, 100, 3500)] * 64

        animator.send_frame(hsbk)

        mock_udp_socket.socket_class.assert_called_once_with(
            socket.AF_INET6, socket.SOCK_DGRAM
        )

    def test_send_frame_uses_ipv6_socket_family_for_zoned_address(
        self, mock_udp_socket: MockUdpSocket
    ) -> None:
        """A zoned link-local target is still IPv6.

        The family now comes from :func:`lifx.network.address.family_for`,
        which parses the literal rather than inspecting its characters, so
        the zone suffix has to survive that round trip.
        """
        animator = Animator(
            ip="fe80::1%1",
            serial=Serial.from_string("d073d5123456"),
            framebuffer=FrameBuffer(pixel_count=64),
            packet_generator=MatrixPacketGenerator(
                tile_count=1, tile_width=8, tile_height=8
            ),
        )
        hsbk: list[tuple[int, int, int, int]] = [(100, 100, 100, 3500)] * 64

        animator.send_frame(hsbk)

        mock_udp_socket.socket_class.assert_called_once_with(
            socket.AF_INET6, socket.SOCK_DGRAM
        )

    def test_send_frame_preserves_zoned_ipv6_scope(
        self, mock_udp_socket: MockUdpSocket
    ) -> None:
        """Animator frames use the native four-field scoped sockaddr."""
        animator = Animator(
            ip="fe80::1%test0",
            serial=Serial.from_string("d073d5123456"),
            framebuffer=FrameBuffer(pixel_count=64),
            packet_generator=MatrixPacketGenerator(
                tile_count=1, tile_width=8, tile_height=8
            ),
        )

        hsbk: list[tuple[int, int, int, int]] = [(100, 100, 100, 3500)] * 64
        with patch("lifx.network.address.socket.if_nametoindex", return_value=7):
            animator.send_frame(hsbk)

        address = mock_udp_socket.sock.sendto.call_args.args[1]
        assert address == ("fe80::1", 56700, 0, 7)

    def test_invalid_named_zone_fails_on_send_as_network_error(self) -> None:
        """Construction is lightweight and first use reports a typed failure."""
        animator = Animator(
            ip="fe80::1%missing0",
            serial=Serial.from_string("d073d5123456"),
            framebuffer=FrameBuffer(pixel_count=64),
            packet_generator=MatrixPacketGenerator(
                tile_count=1, tile_width=8, tile_height=8
            ),
        )
        hsbk: list[tuple[int, int, int, int]] = [(100, 100, 100, 3500)] * 64

        with patch(
            "lifx.network.address.socket.if_nametoindex",
            side_effect=OSError("no such interface"),
        ):
            with pytest.raises(LifxNetworkError, match="Failed to open UDP socket"):
                animator.send_frame(hsbk)

        assert animator._socket is None
        assert animator._addr is None

    def test_invalid_port_fails_before_socket_creation(
        self, mock_udp_socket: MockUdpSocket
    ) -> None:
        """An impossible endpoint is rejected without opening or using a socket."""
        animator = Animator(
            ip="192.0.2.1",
            port=70000,
            serial=Serial.from_string("d073d5123456"),
            framebuffer=FrameBuffer(pixel_count=64),
            packet_generator=MatrixPacketGenerator(
                tile_count=1, tile_width=8, tile_height=8
            ),
        )
        hsbk: list[tuple[int, int, int, int]] = [(100, 100, 100, 3500)] * 64

        with pytest.raises(LifxNetworkError, match="Port must be between"):
            animator.send_frame(hsbk)

        mock_udp_socket.socket_class.assert_not_called()
        mock_udp_socket.sock.sendto.assert_not_called()
        assert animator._socket is None
        assert animator._addr is None

    def test_socket_setup_failure_closes_partial_socket(
        self, animator: Animator, mock_udp_socket: MockUdpSocket
    ) -> None:
        """Failure after descriptor creation closes it before surfacing."""
        mock_udp_socket.sock.setblocking.side_effect = OSError("setup failed")
        hsbk: list[tuple[int, int, int, int]] = [(100, 100, 100, 3500)] * 64

        with pytest.raises(LifxNetworkError, match="Failed to open UDP socket"):
            animator.send_frame(hsbk)

        mock_udp_socket.sock.close.assert_called_once_with()
        assert animator._socket is None
        assert animator._addr is None

    def test_probe_send_failure_preserves_sequence_and_ack_state(
        self, animator: Animator, mock_udp_socket: MockUdpSocket
    ) -> None:
        """Repeated probe failures stay typed and cannot poison the ACK gate."""
        mock_udp_socket.sock.sendto.side_effect = OSError("forced send failure")
        hsbk: list[tuple[int, int, int, int]] = [(100, 100, 100, 3500)] * 64
        initial_sequence = animator._sequence

        for _ in range(2):
            with pytest.raises(
                LifxNetworkError, match="Failed to send animation frame"
            ):
                animator.send_frame(hsbk)

        assert animator._sequence == initial_sequence
        assert animator._ack_gate.outstanding_count == 0
        assert mock_udp_socket.sock.sendto.call_count == 2

    def test_later_probe_failure_preserves_successful_packet_state(
        self, mock_udp_socket: MockUdpSocket
    ) -> None:
        """Earlier sends advance, while a failed final probe stays untracked."""
        animator = Animator(
            ip="192.0.2.1",
            serial=Serial.from_string("d073d5123456"),
            framebuffer=FrameBuffer(pixel_count=128),
            packet_generator=MatrixPacketGenerator(
                tile_count=1, tile_width=16, tile_height=8
            ),
        )
        assert animator._probe_index == 2
        mock_udp_socket.sock.sendto.side_effect = [
            None,
            None,
            OSError("forced final send failure"),
        ]
        hsbk: list[tuple[int, int, int, int]] = [(100, 100, 100, 3500)] * 128
        initial_sequence = animator._sequence

        with pytest.raises(LifxNetworkError, match="Failed to send animation frame"):
            animator.send_frame(hsbk)

        sent_sequences = [
            call.args[0][23] for call in mock_udp_socket.sock.sendto.call_args_list
        ]
        assert sent_sequences == [
            initial_sequence,
            (initial_sequence + 1) % 256,
            (initial_sequence + 2) % 256,
        ]
        assert animator._sequence == (initial_sequence + 2) % 256
        assert animator._ack_gate.outstanding_count == 0

    def test_incomplete_socket_session_fails_without_assertion(
        self, animator: Animator, mock_udp_socket: MockUdpSocket
    ) -> None:
        """The socket/address invariant remains enforced under ``python -O``."""
        animator._socket = mock_udp_socket.sock
        animator._addr = None
        hsbk: list[tuple[int, int, int, int]] = [(100, 100, 100, 3500)] * 64

        with pytest.raises(LifxNetworkError, match="session is incomplete"):
            animator.send_frame(hsbk)

    def test_close_re_resolves_named_zone_for_next_session(
        self, mock_udp_socket: MockUdpSocket
    ) -> None:
        """A new socket session does not reuse a stale interface index."""
        animator = Animator(
            ip="fe80::1%test0",
            serial=Serial.from_string("d073d5123456"),
            framebuffer=FrameBuffer(pixel_count=64),
            packet_generator=MatrixPacketGenerator(
                tile_count=1, tile_width=8, tile_height=8
            ),
        )
        hsbk: list[tuple[int, int, int, int]] = [(100, 100, 100, 3500)] * 64

        with patch(
            "lifx.network.address.socket.if_nametoindex", side_effect=[7, 9]
        ) as lookup:
            animator.send_frame(hsbk)
            animator.close()
            animator.send_frame(hsbk)

        assert lookup.call_count == 2
        addresses = [
            call.args[1] for call in mock_udp_socket.sock.sendto.call_args_list
        ]
        assert addresses[0] == ("fe80::1", 56700, 0, 7)
        assert addresses[-1] == ("fe80::1", 56700, 0, 9)

    def test_close_closes_socket(
        self, animator: Animator, mock_udp_socket: MockUdpSocket
    ) -> None:
        """Test that close() closes the socket."""
        hsbk: list[tuple[int, int, int, int]] = [(100, 100, 100, 3500)] * 64

        animator.send_frame(hsbk)
        animator.close()

        mock_udp_socket.sock.close.assert_called_once()


class TestAnimatorStatsFlowFields:
    """Tests for the additive AnimatorStats flow-control observability fields.

    `getattr(..., default)` keeps attribute access pyright-clean while the
    fields are exercised.
    """

    def test_gated_and_acks_outstanding_default(self) -> None:
        """AnimatorStats(packets_sent=1, total_time_ms=0.5) constructs with
        the additive fields defaulted: stats.gated is False and
        stats.acks_outstanding == 0.
        """
        stats = AnimatorStats(packets_sent=1, total_time_ms=0.5)

        assert getattr(stats, "gated", None) is False
        assert getattr(stats, "acks_outstanding", None) == 0


class TestAnimatorProbeBaking:
    """Tests that the ack-required probe flag is baked ONCE into the correct

    template at Animator construction time, selected by
    `PacketGenerator.probe_template_index` (default 0 = first packet;
    large-tile mode = final CopyFrameBuffer). FLAGS_OFFSET=22,
    ACK_REQUIRED_FLAG=0x02 are hardcoded here (not imported from
    `packets.py`) to keep this file's assertions self-contained.
    """

    def test_standard_matrix_bakes_flag_on_first_template(self) -> None:
        """Standard (<=64 pixel) tile: the ack flag is set on templates[0]
        at construction time, before any frame is ever sent.
        """
        framebuffer = FrameBuffer(pixel_count=64)
        packet_generator = MatrixPacketGenerator(
            tile_count=1, tile_width=8, tile_height=8
        )
        serial = Serial.from_string("d073d5123456")

        animator = Animator(
            ip="192.168.1.100",
            serial=serial,
            framebuffer=framebuffer,
            packet_generator=packet_generator,
        )

        assert animator._templates[0].data[22] & 0x02

    def test_large_tile_bakes_flag_only_on_final_copyfb_template(self) -> None:
        """13x26 large-tile: only the FINAL template (the CopyFrameBuffer,
        `probe_template_index`) carries the flag; every other template's
        flags byte stays 0. The row-aligned chunking produces 7 Set64
        packets plus 1 CopyFB, so the flagged template is index 7.
        """
        framebuffer = FrameBuffer(pixel_count=338)
        packet_generator = MatrixPacketGenerator(
            tile_count=1, tile_width=13, tile_height=26
        )
        serial = Serial.from_string("d073d5123456")

        animator = Animator(
            ip="192.168.1.100",
            serial=serial,
            framebuffer=framebuffer,
            packet_generator=packet_generator,
        )

        probe_index = getattr(packet_generator, "probe_template_index", None)
        assert probe_index == 7
        assert len(animator._templates) == 8
        for i, tmpl in enumerate(animator._templates):
            assert bool(tmpl.data[22] & 0x02) == (i == probe_index)

    def test_for_light_bakes_flag_on_its_single_template(self) -> None:
        """Single Light animator: the one template carries the flag."""
        animator = Light(serial="d073d5123456", ip="192.0.2.10").animator

        assert animator._templates[0].data[22] & 0x02


class TestAnimatorGating:
    """Tests for `send_frame`'s gate-before-framebuffer, latest-frame-wins

    drop, probe tracking and expiry contract. Uses `mock_udp_socket` with no
    acks queued unless a test explicitly queues one; the 8x8 fixture
    animator sends 1 packet/frame, so frame N tracks probe sequence N-1.
    """

    @pytest.fixture
    def animator(self) -> Animator:
        """Create a standard 8x8 (1-packet-per-frame) animator for gating tests."""
        framebuffer = FrameBuffer(pixel_count=64)
        packet_generator = MatrixPacketGenerator(
            tile_count=1, tile_width=8, tile_height=8
        )
        serial = Serial.from_string("d073d5123456")

        return Animator(
            ip="192.168.1.100",
            serial=serial,
            framebuffer=framebuffer,
            packet_generator=packet_generator,
        )

    def test_third_frame_gates_when_no_acks_arrive(
        self, animator: Animator, mock_udp_socket: MockUdpSocket
    ) -> None:
        """Frames 1 and 2 send (gated False, outstanding 1 then 2); frame 3
        is dropped before any packet is queued -- gated True, packets_sent
        0, sendto call_count unchanged (the gate saturates at 2 outstanding
        probes and drops with latest-frame-wins semantics).
        """
        hsbk: list[tuple[int, int, int, int]] = [(100, 100, 100, 3500)] * 64

        stats1 = animator.send_frame(hsbk)
        assert getattr(stats1, "gated", None) is False
        assert stats1.packets_sent == 1
        assert getattr(stats1, "acks_outstanding", None) == 1

        stats2 = animator.send_frame(hsbk)
        assert getattr(stats2, "gated", None) is False
        assert stats2.packets_sent == 1
        assert getattr(stats2, "acks_outstanding", None) == 2

        call_count_before = mock_udp_socket.sock.sendto.call_count
        stats3 = animator.send_frame(hsbk)

        assert getattr(stats3, "gated", None) is True
        assert stats3.packets_sent == 0
        assert mock_udp_socket.sock.sendto.call_count == call_count_before

    def test_gated_frame_skips_framebuffer_apply(
        self, animator: Animator, mock_udp_socket: MockUdpSocket
    ) -> None:
        """A gated frame must not touch `framebuffer.apply` -- the gate
        check happens before any framebuffer work.
        """
        hsbk: list[tuple[int, int, int, int]] = [(100, 100, 100, 3500)] * 64

        animator.send_frame(hsbk)  # outstanding 1
        animator.send_frame(hsbk)  # outstanding 2, gated

        original_apply = animator._require_geometry().framebuffer.apply
        apply_spy = MagicMock(side_effect=original_apply)
        animator._require_geometry().framebuffer.apply = apply_spy  # type: ignore[method-assign]

        animator.send_frame(hsbk)

        apply_spy.assert_not_called()

    def test_wrong_length_raises_even_when_gated(
        self, animator: Animator, mock_udp_socket: MockUdpSocket
    ) -> None:
        """The length-mismatch ValueError takes precedence over the gate
        check: a saturated gate must not suppress input validation, so the
        explicit length check runs ahead of the gate.
        """
        hsbk: list[tuple[int, int, int, int]] = [(100, 100, 100, 3500)] * 64
        animator.send_frame(hsbk)
        animator.send_frame(hsbk)  # gate saturated

        wrong_length: list[tuple[int, int, int, int]] = [(100, 100, 100, 3500)] * 32
        with pytest.raises(ValueError, match="must match pixel_count"):
            animator.send_frame(wrong_length)

    def test_gated_frames_consume_no_sequence_numbers(
        self, animator: Animator, mock_udp_socket: MockUdpSocket
    ) -> None:
        """A gated frame must not advance the sequence counter -- the next
        successful frame's sequence continues contiguously across the drop.
        """
        hsbk: list[tuple[int, int, int, int]] = [(100, 100, 100, 3500)] * 64

        def _last_sent_sequence() -> int:
            call_args = mock_udp_socket.sock.sendto.call_args
            data = call_args[0][0]
            return data[23]

        animator.send_frame(hsbk)  # frame 1
        seq_frame1 = _last_sent_sequence()

        animator.send_frame(hsbk)  # frame 2, gate now saturated
        seq_frame2 = _last_sent_sequence()

        sendto_calls_before = mock_udp_socket.sock.sendto.call_count
        animator.send_frame(hsbk)  # frame 3, gated, dropped, no seq consumed
        assert mock_udp_socket.sock.sendto.call_count == sendto_calls_before

        # Ack frame 1's probe to reopen the gate for frame 4.
        mock_udp_socket.queue_datagram(make_ack_datagram(animator._source, seq_frame1))
        animator.send_frame(hsbk)  # frame 4
        seq_frame4 = _last_sent_sequence()

        assert seq_frame4 == (seq_frame2 + 1) % 256

    def test_ack_for_tracked_probe_reopens_gate(
        self, animator: Animator, mock_udp_socket: MockUdpSocket
    ) -> None:
        """Queuing a correctly addressed ack for a tracked probe sequence
        reopens the gate -- the next `send_frame` sweeps it and sends.
        """
        hsbk: list[tuple[int, int, int, int]] = [(100, 100, 100, 3500)] * 64

        animator.send_frame(hsbk)
        tracked_seq = mock_udp_socket.sock.sendto.call_args[0][0][23]
        animator.send_frame(hsbk)  # gate saturated

        mock_udp_socket.queue_datagram(make_ack_datagram(animator._source, tracked_seq))
        stats3 = animator.send_frame(hsbk)

        assert getattr(stats3, "gated", None) is False
        assert stats3.packets_sent == 1

    def test_foreign_source_ack_does_not_reopen_gate(
        self, animator: Animator, mock_udp_socket: MockUdpSocket
    ) -> None:
        """An ack matching the tracked sequence but from a different uint32
        source must never unlatch the gate.
        """
        hsbk: list[tuple[int, int, int, int]] = [(100, 100, 100, 3500)] * 64

        animator.send_frame(hsbk)
        tracked_seq = mock_udp_socket.sock.sendto.call_args[0][0][23]
        animator.send_frame(hsbk)  # gate saturated

        foreign_source = animator._source + 1
        mock_udp_socket.queue_datagram(make_ack_datagram(foreign_source, tracked_seq))
        stats3 = animator.send_frame(hsbk)

        assert getattr(stats3, "gated", None) is True
        assert stats3.packets_sent == 0

    def test_expiry_reopens_gate_without_acks(
        self, animator: Animator, mock_udp_socket: MockUdpSocket
    ) -> None:
        """After ACK_EXPIRY_SECONDS with zero acks received, the oldest probe
        expires and the gate reopens on its own with zero retransmits.
        Patches `time.monotonic` on the animator module (the project's
        runtime-read idiom) to control elapsed time deterministically.
        """
        hsbk: list[tuple[int, int, int, int]] = [(100, 100, 100, 3500)] * 64

        with patch("lifx.animation.animator.time.monotonic") as mock_monotonic:
            mock_monotonic.side_effect = [1000.0, 1000.0, 1001.6]

            animator.send_frame(hsbk)
            animator.send_frame(hsbk)  # gate saturated
            stats3 = animator.send_frame(hsbk)

        assert getattr(stats3, "gated", None) is False

    def test_close_resets_gate(
        self, animator: Animator, mock_udp_socket: MockUdpSocket
    ) -> None:
        """`close()` resets the gate: saturating outstanding to the limit,
        closing, then sending again creates a fresh socket and sends
        ungated (close() also calls AckGate.reset()).
        """
        hsbk: list[tuple[int, int, int, int]] = [(100, 100, 100, 3500)] * 64

        animator.send_frame(hsbk)
        animator.send_frame(hsbk)  # gate saturated
        animator.close()

        stats = animator.send_frame(hsbk)

        assert getattr(stats, "gated", None) is False
        assert mock_udp_socket.socket_class.call_count == 2

    def test_acks_outstanding_reflects_own_probe(
        self, animator: Animator, mock_udp_socket: MockUdpSocket
    ) -> None:
        """Sent frames report `acks_outstanding` including their own probe:
        1 after the first frame, 2 after the second.
        """
        hsbk: list[tuple[int, int, int, int]] = [(100, 100, 100, 3500)] * 64

        stats1 = animator.send_frame(hsbk)
        assert getattr(stats1, "acks_outstanding", None) == 1

        stats2 = animator.send_frame(hsbk)
        assert getattr(stats2, "acks_outstanding", None) == 2

    def test_send_frame_has_no_flow_control_toggle(self, animator: Animator) -> None:
        """send_frame accepts exactly one positional argument (hsbk) with no
        flow-control parameter, and the internal AckGate facility is never
        exported from `lifx.animation.__init__`.
        """
        sig = inspect.signature(animator.send_frame)
        assert list(sig.parameters) == ["hsbk"]
        assert "AckGate" not in lifx.animation.__all__


@pytest.mark.emulator
class TestAnimatorForMatrixIntegration:
    """Integration tests for a matrix light's own Animator with emulator."""

    async def test_for_matrix_creates_animator(self, emulator_devices) -> None:
        """Test factory method works with real device."""
        # Find the matrix device
        matrix = None
        for device in emulator_devices:
            if isinstance(device, MatrixLight):
                matrix = device
                break

        assert matrix is not None, "No MatrixLight in emulator_devices"

        async with matrix:
            animator = await matrix.animator.prepare()

            assert animator.pixel_count > 0

    async def test_send_frame_sends_packets(self, emulator_devices) -> None:
        """Test send_frame sends packets."""
        matrix = None
        for device in emulator_devices:
            if isinstance(device, MatrixLight):
                matrix = device
                break

        assert matrix is not None

        async with matrix:
            animator = await matrix.animator.prepare()

            # Create frame
            hsbk: list[tuple[int, int, int, int]] = [
                (65535, 65535, 32768, 3500)
            ] * animator.pixel_count
            stats = animator.send_frame(hsbk)

            assert stats.packets_sent >= 1
            # A single frame can never gate at limit 2.
            assert getattr(stats, "gated", None) is False

            animator.close()

    async def test_animation_loop_simulation(self, emulator_devices) -> None:
        """Test multiple frames in sequence."""
        matrix = None
        for device in emulator_devices:
            if isinstance(device, MatrixLight):
                matrix = device
                break

        assert matrix is not None

        async with matrix:
            animator = await matrix.animator.prepare()

            total_packets = 0
            for frame_num in range(5):
                # Create frame with shifting colors
                hsbk: list[tuple[int, int, int, int]] = []
                for i in range(animator.pixel_count):
                    hue = ((i + frame_num * 10) * 1000) % 65536
                    hsbk.append((hue, 65535, 32768, 3500))

                stats = animator.send_frame(hsbk)
                total_packets += stats.packets_sent
                # Observe gating rather than mask it: the
                # localhost emulator acks fast enough that a lengthened
                # inter-frame sleep should never actually gate a frame.
                assert getattr(stats, "gated", None) is False

                # Small delay between frames (localhost ack drain)
                await asyncio.sleep(0.05)

            # Should have sent packets for multiple frames
            assert total_packets >= 5

            animator.close()


@pytest.mark.emulator
class TestAnimatorForMultizoneIntegration:
    """Integration tests for a multizone light's own Animator with emulator."""

    async def test_for_multizone_creates_animator(self, emulator_devices) -> None:
        """Test factory method works with real device."""
        multizone = None
        for device in emulator_devices:
            if isinstance(device, MultiZoneLight):
                multizone = device
                break

        assert multizone is not None, "No MultiZoneLight in emulator_devices"

        async with multizone:
            animator = await multizone.animator.prepare()

            assert animator.pixel_count > 0

            animator.close()

    async def test_send_frame_extended_protocol(self, emulator_devices) -> None:
        """Test extended multizone sends packets."""
        multizone = None
        for device in emulator_devices:
            if isinstance(device, MultiZoneLight):
                multizone = device
                break

        assert multizone is not None

        async with multizone:
            animator = await multizone.animator.prepare()

            hsbk: list[tuple[int, int, int, int]] = [
                (65535, 65535, 32768, 3500)
            ] * animator.pixel_count
            stats = animator.send_frame(hsbk)

            assert stats.packets_sent >= 1

            animator.close()

    async def test_animation_loop_simulation(self, emulator_devices) -> None:
        """Test multiple frames in sequence."""
        multizone = None
        for device in emulator_devices:
            if isinstance(device, MultiZoneLight):
                multizone = device
                break

        assert multizone is not None

        async with multizone:
            animator = await multizone.animator.prepare()

            total_packets = 0
            for frame_num in range(5):
                # Create frame with shifting colors
                hsbk: list[tuple[int, int, int, int]] = []
                for i in range(animator.pixel_count):
                    hue = ((i + frame_num * 10) * 1000) % 65536
                    hsbk.append((hue, 65535, 32768, 3500))

                stats = animator.send_frame(hsbk)
                total_packets += stats.packets_sent
                # Observe gating rather than mask it: the
                # localhost emulator acks fast enough that a lengthened
                # inter-frame sleep should never actually gate a frame.
                assert getattr(stats, "gated", None) is False

                # Small delay between frames (localhost ack drain)
                await asyncio.sleep(0.05)

            # Should have sent packets for multiple frames
            assert total_packets >= 5

            animator.close()


@pytest.mark.emulator
class TestAnimatorFlowControlIntegration:
    """Deterministic end-to-end gating via ack-drop scenarios and explicit

    expiry sleeps, with zero reliance on ack RTT races. Gating is forced
    only via `drop_packets` scenarios; the only sleeps below are the 1.05s
    expiry sleep and fixed localhost drain sleeps.
    """

    async def test_gating_deterministic_when_acks_dropped(
        self, emulator_server_with_scenarios
    ) -> None:
        """With no acks ever collected, outstanding deterministically reaches
        the gate limit: frames 1 and 2 send (gated False), frame 3 is gated
        (gated True).

        The frames are really sent over UDP to the live emulator, but the
        gate must not depend on the emulator actually *dropping* the probe
        acks: under CI load `drop_packets: {45: 1.0}` is not fully reliable,
        and a single ack sneaking through gets swept and drops the outstanding
        count below the gate limit (observed flaky `gated False` with
        `acks_outstanding=2`). Two things are neutralised so accumulation is
        deterministic regardless of ack timing or wall clock: the animator
        socket is wrapped so its ack drain (`recvfrom_into`) raises
        `BlockingIOError` -- no ack is ever collected, while the delegated
        `sendto` still puts real frames on the wire -- and `ACK_EXPIRY_SECONDS`
        is patched to an hour (no probe expires mid-run). Patching these --
        rather than the shared `time.monotonic`, which would wedge the live
        emulator connection's own deadline logic -- keeps the fix isolated to
        the gate. The first frame runs before the wrap purely to create the
        lazily-opened socket instance being wrapped.
        """
        server_info, device_info = await emulator_server_with_scenarios(
            device_type="tile",
            serial="d073d5000007",
            scenarios={"drop_packets": {45: 1.0}},
        )

        matrix = MatrixLight(
            serial=device_info.serial,
            ip="127.0.0.1",
            port=server_info.port,
            timeout=2.0,
            max_retries=2,
        )

        async with matrix:
            animator = await matrix.animator.prepare()

            hsbk: list[tuple[int, int, int, int]] = [
                (65535, 65535, 32768, 3500)
            ] * animator.pixel_count

            # First frame opens the socket and tracks probe 1 (gate still open).
            stats1 = animator.send_frame(hsbk)

            # Wrap the socket so acks are never collected (real sendto still
            # delegates); with expiry also disabled the remaining two sends
            # deterministically saturate the gate.
            animator._socket = MagicMock(wraps=animator._socket)
            animator._socket.recvfrom_into.side_effect = BlockingIOError

            with patch("lifx.animation.flow.ACK_EXPIRY_SECONDS", 3600.0):
                stats2 = animator.send_frame(hsbk)
                stats3 = animator.send_frame(hsbk)

            assert getattr(stats1, "gated", None) is False
            assert getattr(stats2, "gated", None) is False
            assert getattr(stats3, "gated", None) is True

            animator.close()

    async def test_gate_reopens_after_expiry(
        self, emulator_server_with_scenarios
    ) -> None:
        """Continuing from a saturated gate, once outstanding probes exceed
        ACK_EXPIRY_SECONDS the gate reopens on the next frame.

        As in the accumulation test, the animator socket is wrapped so its ack
        drain raises `BlockingIOError` -- no ack is ever collected (the
        emulator `drop_packets` scenario is not reliable enough under CI load)
        while real frames still go out via the delegated `sendto` -- and the
        gate direction is driven through the live-read `ACK_EXPIRY_SECONDS`
        constant rather than the wall clock: saturate with expiry disabled (an
        hour), then drop it below the elapsed time so the next frame's `sweep`
        deterministically prunes both probes and reopens the gate. Patching
        these -- not the shared `time.monotonic` -- avoids disturbing the live
        emulator connection's deadline logic. The first frame runs before the
        wrap purely to create the lazily-opened socket instance being wrapped.
        """
        server_info, device_info = await emulator_server_with_scenarios(
            device_type="tile",
            serial="d073d5000007",
            scenarios={"drop_packets": {45: 1.0}},
        )

        matrix = MatrixLight(
            serial=device_info.serial,
            ip="127.0.0.1",
            port=server_info.port,
            timeout=2.0,
            max_retries=2,
        )

        async with matrix:
            animator = await matrix.animator.prepare()
            hsbk: list[tuple[int, int, int, int]] = [
                (65535, 65535, 32768, 3500)
            ] * animator.pixel_count

            # First frame opens the socket and tracks probe 1 (gate still open).
            animator.send_frame(hsbk)

            # Wrap the socket so acks are never collected for the rest of the
            # test (real sendto still delegates).
            animator._socket = MagicMock(wraps=animator._socket)
            animator._socket.recvfrom_into.side_effect = BlockingIOError

            # Saturate the gate with expiry effectively disabled.
            with patch("lifx.animation.flow.ACK_EXPIRY_SECONDS", 3600.0):
                animator.send_frame(hsbk)
                gated_stats = animator.send_frame(hsbk)
            assert getattr(gated_stats, "gated", None) is True

            # Next sweep sees every probe as expired (negative threshold), so
            # the gate reopens without a wall-clock sleep.
            with patch("lifx.animation.flow.ACK_EXPIRY_SECONDS", -1.0):
                reopened_stats = animator.send_frame(hsbk)
            assert getattr(reopened_stats, "gated", None) is False

            animator.close()

    async def test_acks_collected_on_healthy_emulator(self, emulator_devices) -> None:
        """On a healthy emulator (no drop scenario), streaming 5 frames with
        a 0.1s inter-frame sleep keeps every frame gated False, and from
        frame 2 onward each sent frame's acks_outstanding == 1 (the prior
        probe was swept, only this frame's own probe remains tracked) --
        proves ack collection through the animator's own socket.
        """
        matrix = None
        for device in emulator_devices:
            if isinstance(device, MatrixLight):
                matrix = device
                break
        assert matrix is not None

        async with matrix:
            animator = await matrix.animator.prepare()
            hsbk: list[tuple[int, int, int, int]] = [
                (65535, 65535, 32768, 3500)
            ] * animator.pixel_count

            for frame_num in range(5):
                stats = animator.send_frame(hsbk)
                assert getattr(stats, "gated", None) is False
                if frame_num >= 1:
                    assert getattr(stats, "acks_outstanding", None) == 1
                await _drain_probe_acks(animator)

            animator.close()

    async def test_large_tile_13x26_framebuffer_path(
        self, large_tile_matrix_device
    ) -> None:
        """13x26 large-tile path (needs plans 04-03 AND 04-04): pixel_count
        is 338, the first frame sends 8 packets (7 row-aligned Set64 + 1
        CopyFB), and after the CopyFB probe is acked and swept, a second
        frame (once that ack has drained) is gated False with
        acks_outstanding < 2.
        """
        matrix = large_tile_matrix_device

        async with matrix:
            animator = await matrix.animator.prepare()
            assert animator.pixel_count == 338

            hsbk: list[tuple[int, int, int, int]] = [
                (65535, 65535, 32768, 3500)
            ] * animator.pixel_count

            stats1 = animator.send_frame(hsbk)
            assert stats1.packets_sent == 8

            await _drain_probe_acks(animator)

            stats2 = animator.send_frame(hsbk)
            assert getattr(stats2, "gated", None) is False
            assert getattr(stats2, "acks_outstanding", 0) < 2

            animator.close()


@pytest.mark.emulator
class TestAnimatorErrorHandling:
    """Integration tests for Animator error handling."""

    async def test_send_frame_wrong_length_raises(self, emulator_devices) -> None:
        """Test wrong Color array length raises error."""
        matrix = None
        for device in emulator_devices:
            if isinstance(device, MatrixLight):
                matrix = device
                break

        assert matrix is not None

        async with matrix:
            animator = await matrix.animator.prepare()

            # Wrong length
            hsbk: list[tuple[int, int, int, int]] = [(100, 100, 100, 3500)] * (
                animator.pixel_count // 2
            )

            with pytest.raises(ValueError, match="must match"):
                animator.send_frame(hsbk)

            animator.close()
