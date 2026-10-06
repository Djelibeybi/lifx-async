"""Ring geometry helpers shared by the effects that draw on a Mirror ring."""

from __future__ import annotations

import pytest

from lifx.effects.ring import fold_at_zone_zero, ring_distance, ring_index, ring_offset


class TestRingDistance:
    @pytest.mark.parametrize(
        ("zone", "expected"),
        [(0, 0), (1, 1), (12, 12), (13, 12), (24, 1), (25, 0)],
    )
    def test_it_measures_the_short_way_round_a_ring_of_25(
        self, zone: int, expected: int
    ) -> None:
        assert ring_distance(zone, 25) == expected

    def test_it_keeps_a_float_distance_a_float(self) -> None:
        assert ring_distance(23.5, 25) == pytest.approx(1.5)


class TestRingOffset:
    @pytest.mark.parametrize(
        ("offset", "expected"),
        [(0.0, 0.0), (3.0, 3.0), (-3.0, -3.0), (24.0, -1.0), (-24.0, 1.0), (5.0, 5.0)],
    )
    def test_it_folds_a_signed_offset_onto_the_short_way_round(
        self, offset: float, expected: float
    ) -> None:
        assert ring_offset(offset, 25) == pytest.approx(expected)


class TestRingIndex:
    def test_a_ring_wraps_a_position_beyond_either_end(self) -> None:
        assert ring_index(26.7, 25, wraps=True) == 1
        assert ring_index(-1.0, 25, wraps=True) == 24

    def test_a_strip_clamps_a_position_beyond_either_end(self) -> None:
        assert ring_index(26.7, 25, wraps=False) == 24
        assert ring_index(-3.0, 25, wraps=False) == 0

    def test_both_keep_a_position_inside_the_zones(self) -> None:
        assert ring_index(7.9, 25, wraps=True) == 7
        assert ring_index(7.9, 25, wraps=False) == 7


class TestFoldAtZoneZero:
    def test_it_makes_the_pixels_symmetric_about_zone_zero(self) -> None:
        folded = fold_at_zone_zero(list(range(6)))
        assert folded == [0, 1, 2, 3, 2, 1]
