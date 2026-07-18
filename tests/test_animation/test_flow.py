"""RED branch-matrix suite pinning the AckGate flow-control contract.

`src/lifx/animation/flow.py` does not exist yet -- importing it below fails
at collection, which is this file's intended RED. This suite defines GREEN
for plan 04-04 Task 1: the exact `AckGate` API (constants, `track`, `sweep`,
`reset`, `gated`, `outstanding_count`) that the animator's gate-before-frame
contract depends on.

See `.planning/phases/04-animation-flow-control/04-RESEARCH.md` -- "AckGate
facility" code example and "Branch matrix for 100% branch patch coverage".

All timing uses explicit `now` float arguments -- no sleeps anywhere.
"""

from __future__ import annotations

from lifx.animation.flow import (
    ACK_EXPIRY_SECONDS,
    ACK_INFLIGHT_LIMIT,
    ACK_PKT_TYPE,
    AckGate,
)
from tests.test_animation.conftest import MockUdpSocket, make_ack_datagram

# Arbitrary uint32 source used throughout the matrix.
SOURCE = 0x12AB34CD


class TestAckGateConstants:
    """Pins the spike-003-measured tuning constants (D4-01)."""

    def test_constants_have_spike_measured_values(self) -> None:
        """ACK_PKT_TYPE=45, ACK_INFLIGHT_LIMIT=2, ACK_EXPIRY_SECONDS=1.0."""
        assert ACK_PKT_TYPE == 45
        assert ACK_INFLIGHT_LIMIT == 2
        assert ACK_EXPIRY_SECONDS == 1.0


class TestAckGateState:
    """Pins `track`/`reset`/`gated`/`outstanding_count` state transitions."""

    def test_fresh_gate_is_not_gated(self) -> None:
        """A newly constructed gate has no outstanding probes and is open."""
        gate = AckGate()

        assert gate.gated is False
        assert gate.outstanding_count == 0

    def test_track_gates_at_inflight_limit(self) -> None:
        """Gate opens below the limit, closes at exactly ACK_INFLIGHT_LIMIT."""
        gate = AckGate()
        now = 1000.0

        gate.track(5, now)
        assert gate.outstanding_count == 1
        assert gate.gated is False

        gate.track(6, now)
        assert gate.outstanding_count == 2
        assert gate.gated is True

    def test_track_wrap_collision_overwrites(self) -> None:
        """A sequence-number collision overwrites the stale entry (D4-01:

        errs towards sending, never towards stalling -- self-healing).
        """
        gate = AckGate()

        gate.track(5, 1000.0)
        gate.track(5, 1000.5)  # wraps back to the same sequence byte

        assert gate.outstanding_count == 1

    def test_reset_clears_everything(self) -> None:
        """`reset()` clears all outstanding probes and reopens the gate."""
        gate = AckGate()
        gate.track(5, 1000.0)
        gate.track(6, 1000.0)
        assert gate.gated is True

        gate.reset()

        assert gate.gated is False
        assert gate.outstanding_count == 0


class TestAckGateSweep:
    """Pins the untrusted-datagram sweep/drain-loop branch matrix."""

    def test_sweep_empty_socket_is_a_noop(self, mock_udp_socket: MockUdpSocket) -> None:
        """An immediate BlockingIOError (no datagrams) leaves state unchanged."""
        gate = AckGate()
        gate.track(5, 1000.0)

        gate.sweep(mock_udp_socket.sock, SOURCE, 1000.0)

        assert gate.outstanding_count == 1

    def test_sweep_matching_ack_reopens_gate(
        self, mock_udp_socket: MockUdpSocket
    ) -> None:
        """A correctly addressed ack for a tracked sequence pops it and

        reopens the gate once outstanding drops below the limit.
        """
        gate = AckGate()
        gate.track(5, 1000.0)
        gate.track(6, 1000.0)
        assert gate.gated is True

        mock_udp_socket.queue_datagram(make_ack_datagram(SOURCE, 5))
        gate.sweep(mock_udp_socket.sock, SOURCE, 1000.01)

        assert gate.outstanding_count == 1
        assert gate.gated is False

    def test_sweep_drains_multiple_datagrams_in_one_call(
        self, mock_udp_socket: MockUdpSocket
    ) -> None:
        """All queued datagrams are drained within a single `sweep()` call."""
        gate = AckGate()
        gate.track(5, 1000.0)
        gate.track(6, 1000.0)
        gate.track(7, 1000.0)

        mock_udp_socket.queue_datagram(make_ack_datagram(SOURCE, 5))
        mock_udp_socket.queue_datagram(make_ack_datagram(SOURCE, 6))
        mock_udp_socket.queue_datagram(make_ack_datagram(SOURCE, 7))
        gate.sweep(mock_udp_socket.sock, SOURCE, 1000.01)

        assert gate.outstanding_count == 0

    def test_sweep_ack_for_untracked_sequence_ignored(
        self, mock_udp_socket: MockUdpSocket
    ) -> None:
        """An ack for a sequence that was never tracked is ignored."""
        gate = AckGate()
        gate.track(5, 1000.0)

        mock_udp_socket.queue_datagram(make_ack_datagram(SOURCE, 99))
        gate.sweep(mock_udp_socket.sock, SOURCE, 1000.01)

        assert gate.outstanding_count == 1

    def test_sweep_runt_datagram_ignored_then_valid_ack_processed(
        self, mock_udp_socket: MockUdpSocket
    ) -> None:
        """A runt (<36 byte) datagram is ignored; the sweep continues to

        drain a following valid ack in the same call.
        """
        gate = AckGate()
        gate.track(5, 1000.0)
        gate.track(6, 1000.0)
        assert gate.gated is True

        mock_udp_socket.queue_datagram(make_ack_datagram(SOURCE, 5, size=20))
        mock_udp_socket.queue_datagram(make_ack_datagram(SOURCE, 5))
        gate.sweep(mock_udp_socket.sock, SOURCE, 1000.01)

        assert gate.outstanding_count == 1
        assert gate.gated is False

    def test_sweep_wrong_pkt_type_ignored(self, mock_udp_socket: MockUdpSocket) -> None:
        """A datagram with the correct source/sequence but the wrong

        pkt_type (e.g. 3 = StateService) is ignored.
        """
        gate = AckGate()
        gate.track(5, 1000.0)

        mock_udp_socket.queue_datagram(make_ack_datagram(SOURCE, 5, pkt_type=3))
        gate.sweep(mock_udp_socket.sock, SOURCE, 1000.01)

        assert gate.outstanding_count == 1

    def test_sweep_wrong_source_ignored(self, mock_udp_socket: MockUdpSocket) -> None:
        """Another client's traffic (matching seq, different uint32 source)

        must never unlatch the gate.
        """
        gate = AckGate()
        gate.track(5, 1000.0)
        foreign_source = SOURCE + 1

        mock_udp_socket.queue_datagram(make_ack_datagram(foreign_source, 5))
        gate.sweep(mock_udp_socket.sock, SOURCE, 1000.01)

        assert gate.outstanding_count == 1

    def test_sweep_os_error_returns_cleanly(
        self, mock_udp_socket: MockUdpSocket
    ) -> None:
        """`recvfrom_into` raising OSError (e.g. Windows WSAECONNRESET after

        an ICMP port-unreachable) must not crash the sweep; state is
        unchanged and the next frame's sweep tries again.
        """
        gate = AckGate()
        gate.track(5, 1000.0)
        mock_udp_socket.sock.recvfrom_into.side_effect = OSError(
            "simulated WSAECONNRESET"
        )

        gate.sweep(mock_udp_socket.sock, SOURCE, 1000.01)

        assert gate.outstanding_count == 1


class TestAckGateExpiry:
    """Pins the expiry branch matrix -- explicit `now`, zero sleeping."""

    def test_expired_entry_is_pruned(self, mock_udp_socket: MockUdpSocket) -> None:
        """An entry older than ACK_EXPIRY_SECONDS is pruned, freeing the

        gate slot (zero retransmits by design -- an expired probe just
        frees the slot).
        """
        gate = AckGate()
        gate.track(5, 1000.0)

        gate.sweep(mock_udp_socket.sock, SOURCE, 1000.0 + 1.5)

        assert gate.outstanding_count == 0

    def test_fresh_entry_is_retained(self, mock_udp_socket: MockUdpSocket) -> None:
        """An entry younger than ACK_EXPIRY_SECONDS is retained."""
        gate = AckGate()
        gate.track(5, 1000.0)

        gate.sweep(mock_udp_socket.sock, SOURCE, 1000.0 + 0.5)

        assert gate.outstanding_count == 1

    def test_mixed_expiry_prunes_only_the_expired_entry(
        self, mock_udp_socket: MockUdpSocket
    ) -> None:
        """Of one expired and one fresh entry, only the expired one is

        pruned and the gate reopens.
        """
        gate = AckGate()
        gate.track(5, 1000.0)
        gate.track(6, 1000.6)
        assert gate.gated is True

        gate.sweep(mock_udp_socket.sock, SOURCE, 1000.0 + 1.5)

        assert gate.outstanding_count == 1
        assert gate.gated is False
