"""Tests for IdleDeadline utility class."""

from __future__ import annotations

from lifx.network.utils import IdleDeadline


class TestIdleDeadline:
    """Tests for the IdleDeadline dual-deadline timer."""

    def test_idle_deadline_remaining_positive_on_construction(self) -> None:
        """remaining() should be positive immediately after construction."""
        deadline = IdleDeadline(timeout=5.0, idle_timeout=2.0)
        assert deadline.remaining() > 0
