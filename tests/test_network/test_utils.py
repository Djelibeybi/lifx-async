"""Tests for IdleDeadline utility class."""

from __future__ import annotations

from unittest.mock import patch

from lifx.network.utils import IdleDeadline


class TestIdleDeadline:
    """Tests for the IdleDeadline dual-deadline timer."""

    def test_idle_deadline_remaining_positive_on_construction(self) -> None:
        """remaining() should be positive immediately after construction."""
        deadline = IdleDeadline(timeout=5.0, idle_timeout=2.0)
        assert deadline.remaining() > 0

    def test_idle_deadline_overall_expires(self) -> None:
        """overall_expired is True and remaining() <= 0 once timeout has elapsed."""
        # Construction reads monotonic once (t=0); subsequent calls return t=6.
        times = iter(
            [
                0.0,  # __init__: _start (and _last_response = _start)
                6.0,  # remaining(): now=6; overall elapsed=6 > timeout=5
                6.0,  # overall_expired: now=6
            ]
        )

        with patch("lifx.network.utils.time.monotonic", side_effect=times):
            deadline = IdleDeadline(timeout=5.0, idle_timeout=2.0)
            assert deadline.remaining() <= 0
            assert deadline.overall_expired is True

    def test_idle_deadline_idle_expires(self) -> None:
        """idle_expired is True and remaining() <= 0 after idle_timeout elapses."""
        # Advance past idle_timeout (2 s) but stay within overall timeout (5 s).
        times = iter(
            [
                0.0,  # __init__: _start (and _last_response = _start)
                3.0,  # remaining(): now=3; idle elapsed=3 > idle_timeout=2
                3.0,  # idle_expired: now=3
                3.0,  # overall_expired: now=3
            ]
        )

        with patch("lifx.network.utils.time.monotonic", side_effect=times):
            deadline = IdleDeadline(timeout=5.0, idle_timeout=2.0)
            assert deadline.remaining() <= 0
            assert deadline.idle_expired is True
            assert deadline.overall_expired is False

    def test_idle_deadline_mark_response_resets_idle(self) -> None:
        """mark_response() resets the idle clock, extending remaining()."""
        times = iter(
            [
                0.0,  # __init__: _start (and _last_response = _start)
                1.0,  # mark_response(): _last_response = 1.0
                1.5,  # remaining(): now=1.5; idle elapsed=0.5 < idle_timeout=2
            ]
        )

        with patch("lifx.network.utils.time.monotonic", side_effect=times):
            deadline = IdleDeadline(timeout=5.0, idle_timeout=2.0)
            deadline.mark_response()
            remaining = deadline.remaining()
            # Overall remaining = 5.0 - 1.5 = 3.5; idle remaining = 2.0 - 0.5 = 1.5
            assert remaining > 0
            assert remaining <= 2.0  # idle remaining (1.5) is the binding constraint

    def test_idle_deadline_overall_caps_idle(self) -> None:
        """remaining() is capped by overall when overall is nearly exhausted."""
        # Idle remaining = 1.95 s, but overall is nearly exhausted at 0.05 s.
        times = iter(
            [
                0.0,  # __init__: _start (and _last_response = _start)
                4.9,  # mark_response(): _last_response = 4.9
                4.95,  # remaining(): now=4.95; idle elapsed=0.05; overall elapsed=4.95
            ]
        )

        with patch("lifx.network.utils.time.monotonic", side_effect=times):
            deadline = IdleDeadline(timeout=5.0, idle_timeout=2.0)
            deadline.mark_response()
            remaining = deadline.remaining()
            # Idle remaining = 2.0 - 0.05 = 1.95; overall remaining = 5.0 - 4.95 = 0.05
            # remaining() must return the minimum: ~0.05, not 1.95
            assert remaining < 1.0  # capped by overall (0.05), not idle (1.95)
            assert remaining > 0  # not yet expired

    def test_expired_convenience_property(self) -> None:
        """`expired` is True once either deadline fires, False otherwise."""
        # Shortly after construction: neither idle nor overall expired.
        with patch("lifx.network.utils.time.monotonic", side_effect=[0.0, 1.0, 1.0]):
            deadline = IdleDeadline(timeout=5.0, idle_timeout=2.0)
            assert deadline.expired is False

        # Past the idle timeout: expired short-circuits True on idle_expired.
        with patch("lifx.network.utils.time.monotonic", side_effect=[0.0, 3.0]):
            deadline = IdleDeadline(timeout=5.0, idle_timeout=2.0)
            assert deadline.expired is True
