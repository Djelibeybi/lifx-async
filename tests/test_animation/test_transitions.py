"""Tests for the transition clipping helper."""

from __future__ import annotations

from lifx.animation.transitions import (
    MIN_TRANSITION_SECONDS,
    TransitionWrite,
    clip_transitions,
)


def w(time: float, target: str, duration: float) -> TransitionWrite:
    return TransitionWrite(time, target, duration)


class TestClipTransitions:
    def test_empty_sequence_returns_empty(self) -> None:
        assert clip_transitions([]) == []

    def test_overlapping_writes_on_one_target_are_clipped_to_the_gap(self) -> None:
        out = clip_transitions([w(0.0, "a", 2.0), w(1.25, "a", 2.0)])
        assert out == [w(0.0, "a", 1.25), w(1.25, "a", 2.0)]

    def test_fade_shorter_than_the_gap_is_untouched(self) -> None:
        writes = [w(0.0, "a", 0.5), w(1.0, "a", 0.5)]
        assert clip_transitions(writes) == writes

    def test_interleaved_targets_do_not_clip_each_other(self) -> None:
        writes = [w(0.0, "a", 1.0), w(0.1, "b", 1.0), w(0.2, "a", 1.0)]
        out = clip_transitions(writes)
        assert out == [w(0.0, "a", 0.2), w(0.1, "b", 1.0), w(0.2, "a", 1.0)]

    def test_instant_writes_are_kept(self) -> None:
        writes = [w(0.0, "a", 0.0), w(0.001, "a", 0.0)]
        assert clip_transitions(writes) == writes

    def test_write_with_less_than_the_minimum_gap_is_removed(self) -> None:
        out = clip_transitions([w(0.0, "a", 1.0), w(0.019, "a", 1.0)])
        assert out == [w(0.019, "a", 1.0)]

    def test_write_with_exactly_the_minimum_gap_is_kept(self) -> None:
        out = clip_transitions([w(0.0, "a", 1.0), w(MIN_TRANSITION_SECONDS, "a", 1.0)])
        assert len(out) == 2
        assert out[0].duration == MIN_TRANSITION_SECONDS

    def test_same_time_writes_remove_the_earlier(self) -> None:
        out = clip_transitions([w(1.0, "a", 1.0), w(1.0, "a", 1.0)])
        assert out == [w(1.0, "a", 1.0)]

    def test_input_order_is_preserved_and_input_not_mutated(self) -> None:
        writes = [w(0.5, "b", 1.0), w(0.0, "a", 9.0), w(2.0, "a", 1.0)]
        out = clip_transitions(writes)
        assert out == [w(0.5, "b", 1.0), w(0.0, "a", 2.0), w(2.0, "a", 1.0)]
        assert writes[1].duration == 9.0
