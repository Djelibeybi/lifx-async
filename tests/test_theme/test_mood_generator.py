"""Tests for MoodGenerator, the app-style mood renderer."""

from __future__ import annotations

import random

import pytest

from lifx.color import HSBK
from lifx.theme import MoodGenerator, Theme

RED = HSBK(hue=0, saturation=1.0, brightness=1.0, kelvin=3500)
GREEN = HSBK(hue=120, saturation=1.0, brightness=1.0, kelvin=3500)
BLUE = HSBK(hue=240, saturation=1.0, brightness=1.0, kelvin=3500)
DIM_BLUE = HSBK(hue=240, saturation=1.0, brightness=0.5, kelvin=3500)
WHITE = HSBK(hue=0, saturation=0.0, brightness=1.0, kelvin=4000)


def make(colors: list[HSBK], static_mode: str | None = None) -> MoodGenerator:
    return MoodGenerator(
        Theme(colors, static_mode=static_mode),  # type: ignore[arg-type]
        rng=random.Random(1),
    )


class TestStretch:
    def test_same_length_is_unchanged(self) -> None:
        assert MoodGenerator._stretch([RED, GREEN], 2) == [RED, GREEN]

    def test_grows_runs_by_weight(self) -> None:
        # runs R2 G1 B1 into 8: ceil(8*2/4)=4, 2, 2
        assert MoodGenerator._stretch([RED, RED, GREEN, BLUE], 8) == (
            [RED] * 4 + [GREEN] * 2 + [BLUE] * 2
        )

    def test_shrinks_runs_by_weight(self) -> None:
        assert MoodGenerator._stretch([RED] * 8 + [GREEN] * 8, 4) == [
            RED,
            RED,
            GREEN,
            GREEN,
        ]

    def test_stretch_trims_more_runs_than_cells(self) -> None:
        # ceil(2/3)=1 each, total 3, one copy removed from the first run
        assert MoodGenerator._stretch([RED, GREEN, BLUE], 2) == [GREEN, BLUE]

    def test_one_colour(self) -> None:
        assert MoodGenerator._stretch([RED], 5) == [RED] * 5


class TestRescale:
    def test_brightest_matches_light(self) -> None:
        out = MoodGenerator._rescale([RED, DIM_BLUE], 0.4)
        assert out[0].brightness == pytest.approx(0.4, abs=1e-4)
        assert out[1].brightness == pytest.approx(0.2, abs=1e-4)
        assert out[0].hue == RED.hue

    def test_floor_keeps_visible_entries_visible(self) -> None:
        faint = HSBK(hue=0, saturation=1.0, brightness=0.02, kelvin=3500)
        out = MoodGenerator._rescale([RED, faint], 0.1)
        assert out[1].brightness == pytest.approx(0.01, abs=1e-4)

    def test_dark_entry_stays_dark(self) -> None:
        dark = HSBK(hue=0, saturation=1.0, brightness=0.0, kelvin=3500)
        out = MoodGenerator._rescale([RED, dark], 0.1)
        assert out[1].brightness == 0.0

    def test_rescale_zero_brightness_keeps_theme_brightness(self) -> None:
        assert MoodGenerator._rescale([RED, DIM_BLUE], 0.0) == [RED, DIM_BLUE]

    def test_all_dark_theme_is_unchanged(self) -> None:
        dark = HSBK(hue=0, saturation=1.0, brightness=0.0, kelvin=3500)
        assert MoodGenerator._rescale([dark], 0.5) == [dark]


class TestGradient:
    def test_length_and_endpoints(self) -> None:
        out = make([RED, BLUE])._gradient([RED, BLUE], 4)
        assert len(out) == 4
        assert out[0] == RED

    def test_segments_get_remainder_at_the_end(self) -> None:
        # 3 colours -> 2 segments over 5 cells: lengths 2 and 3
        out = make([RED, GREEN, BLUE])._gradient([RED, GREEN, BLUE], 5)
        assert out[0] == RED
        assert out[2] == GREEN

    def test_hue_takes_the_short_way_round(self) -> None:
        a = HSBK(hue=350, saturation=1.0, brightness=1.0, kelvin=3500)
        b = HSBK(hue=10, saturation=1.0, brightness=1.0, kelvin=3500)
        mid = MoodGenerator._interpolate(a, b, 0.5)
        assert min(mid.hue, 360 - mid.hue) == pytest.approx(0, abs=1)

    def test_white_carries_no_hue(self) -> None:
        mid = MoodGenerator._interpolate(WHITE, BLUE, 0.5)
        assert mid.hue == pytest.approx(240, abs=1)

    def test_one_colour_fills(self) -> None:
        assert make([RED])._gradient([RED], 3) == [RED] * 3

    def test_zero_cells(self) -> None:
        assert make([RED, BLUE])._gradient([RED, BLUE], 0) == []


class TestMix:
    def test_circular_mean_wraps(self) -> None:
        a = HSBK(hue=350, saturation=1.0, brightness=1.0, kelvin=3500)
        b = HSBK(hue=10, saturation=1.0, brightness=1.0, kelvin=3500)
        mixed = MoodGenerator._mix([a, b], [1, 1])
        assert min(mixed.hue, 360 - mixed.hue) == pytest.approx(0, abs=1)

    def test_whites_do_not_pull_hue(self) -> None:
        mixed = MoodGenerator._mix([WHITE, BLUE], [3, 1])
        assert mixed.hue == pytest.approx(240, abs=1)

    def test_all_white_has_hue_zero(self) -> None:
        assert MoodGenerator._mix([WHITE, WHITE], [1, 1]).hue == 0


class TestMultizone:
    def test_grid_static_stretches_in_order(self) -> None:
        out = make([RED, GREEN], "grid_static").get_multizone_colors(4, 1.0)
        assert out == [RED, RED, GREEN, GREEN]

    @pytest.mark.parametrize("mode", ["solid_static", "solid_loop"])
    def test_stripe_modes_stretch_in_order(self, mode: str) -> None:
        out = make([RED, GREEN, BLUE], mode).get_multizone_colors(3, 1.0)
        assert out == [RED, GREEN, BLUE]

    def test_solid_uses_distinct_colours(self) -> None:
        out = make([RED, RED, GREEN], "solid").get_multizone_colors(4, 1.0)
        assert sorted({c.hue for c in out}) == [0, 120]
        assert len(out) == 4

    def test_blended_is_a_gradient_over_the_zones(self) -> None:
        out = make([RED, BLUE], "blended").get_multizone_colors(6, 1.0)
        assert len(out) == 6
        assert out[0] in (RED, BLUE)

    def test_unknown_or_missing_mode_is_blended(self) -> None:
        gen = MoodGenerator(Theme([RED, BLUE]), rng=random.Random(1))
        assert len(gen.get_multizone_colors(6, 1.0)) == 6

    def test_rescaled_to_brightness(self) -> None:
        out = make([RED, GREEN], "grid_static").get_multizone_colors(2, 0.5)
        assert max(c.brightness for c in out) == pytest.approx(0.5, abs=1e-4)


class TestBulbs:
    def test_deals_distinct_colours_in_turn(self) -> None:
        out = make([RED, RED, GREEN]).get_bulb_colors([1.0, 1.0, 1.0])
        assert {out[0].hue, out[1].hue} == {0, 120}
        assert out[2] == out[0]

    def test_each_bulb_rescales_to_its_own_brightness(self) -> None:
        out = make([RED, DIM_BLUE]).get_bulb_colors([0.8, 0.8])
        by_hue = {c.hue: c.brightness for c in out}
        assert by_hue[0] == pytest.approx(0.8, abs=1e-4)
        assert by_hue[240] == pytest.approx(0.4, abs=1e-4)

    def test_no_bulbs(self) -> None:
        assert make([RED]).get_bulb_colors([]) == []


class TestMorphPalette:
    def test_sixteen_or_fewer_is_unchanged(self) -> None:
        palette = [RED, GREEN, BLUE]
        assert MoodGenerator.morph_palette(palette) == palette

    def test_reduces_by_run_weight(self) -> None:
        palette = [RED] * 48 + [BLUE] * 16
        out = MoodGenerator.morph_palette(palette)
        assert out == [RED] * 12 + [BLUE] * 4


class TestMatrixRecipes:
    def test_grid_is_serpentine(self) -> None:
        cells = [
            HSBK(hue=i * 10, saturation=1.0, brightness=1.0, kelvin=3500)
            for i in range(6)
        ]
        out = MoodGenerator._grid(cells, 3, 2)
        assert [c.hue for c in out] == [0, 10, 20, 50, 40, 30]

    def test_stripes_repeat_one_row(self) -> None:
        out = MoodGenerator._stripes([RED, GREEN], 4, 3)
        assert out == [RED, RED, GREEN, GREEN] * 3

    def test_edge_walk_order(self) -> None:
        cells = MoodGenerator._edge_cells(4, 3)
        assert cells == [
            (0, 0),
            (0, 1),
            (0, 2),
            (0, 3),
            (1, 0),
            (1, 3),
            (2, 3),
            (2, 2),
            (2, 1),
            (2, 0),
        ]
        assert len(cells) == 2 * (4 - 2) + 2 * 3

    def test_blended_matrix_edges_follow_the_gradient(self) -> None:
        gen = make([RED, BLUE], "blended")
        out = gen._blended_matrix([RED, BLUE], 4, 4)
        assert len(out) == 16
        assert out[0] in (RED, BLUE)

    def test_blended_matrix_interior_is_a_mix(self) -> None:
        gen = make([RED], "blended")
        out = gen._blended_matrix([RED], 3, 3)
        assert out[4].hue == pytest.approx(0, abs=1)

    @pytest.mark.parametrize(("width", "height"), [(1, 5), (5, 1), (1, 1)])
    def test_blended_matrix_degenerate_geometry(self, width: int, height: int) -> None:
        out = make([RED, BLUE], "blended")._blended_matrix([RED, BLUE], width, height)
        assert len(out) == width * height

    def test_get_matrix_colors_grid(self) -> None:
        out = make([RED, GREEN], "grid_static").get_matrix_colors(2, 2, 1.0)
        assert out == [RED, RED, GREEN, GREEN]

    def test_get_matrix_colors_solid_static_is_vertical_stripes(self) -> None:
        out = make([RED, GREEN], "solid_static").get_matrix_colors(2, 2, 1.0)
        assert out == [RED, GREEN, RED, GREEN]

    def test_get_matrix_colors_solid_loop_matches_solid_static(self) -> None:
        a = make([RED, GREEN], "solid_loop").get_matrix_colors(4, 2, 1.0)
        b = make([RED, GREEN], "solid_static").get_matrix_colors(4, 2, 1.0)
        assert a == b

    def test_get_matrix_colors_solid_uses_distinct(self) -> None:
        out = make([RED, RED, GREEN], "solid").get_matrix_colors(4, 1, 1.0)
        assert {c.hue for c in out} == {0, 120}

    def test_get_matrix_colors_blended_size(self) -> None:
        assert len(make([RED, BLUE]).get_matrix_colors(5, 6, 1.0)) == 30

    def test_get_matrix_colors_one_colour(self) -> None:
        out = make([RED], "blended").get_matrix_colors(4, 4, 1.0)
        assert all(c.hue == pytest.approx(0, abs=1) for c in out)


class TestChain:
    def test_grid_spans_the_chain_in_order(self) -> None:
        cells = [
            HSBK(hue=i * 20, saturation=1.0, brightness=1.0, kelvin=3500)
            for i in range(4)
        ]
        # 2 tiles of 1x2: canvas is 2 wide, 2 high, serpentine
        out = make(cells, "grid_static").get_chain_colors(2, 1, 2, 1.0)
        assert [[c.hue for c in tile] for tile in out] == [[0, 60], [20, 40]]

    def test_blended_paints_each_tile_on_its_own(self) -> None:
        out = make([RED, BLUE], "blended").get_chain_colors(3, 4, 4, 1.0)
        assert [len(tile) for tile in out] == [16, 16, 16]

    def test_rescale_spans_the_whole_chain(self) -> None:
        out = make([RED, DIM_BLUE], "solid_static").get_chain_colors(2, 1, 1, 0.5)
        assert max(c.brightness for tile in out for c in tile) == pytest.approx(
            0.5, abs=1e-4
        )
        assert out[1][0].brightness == pytest.approx(0.25, abs=1e-4)
