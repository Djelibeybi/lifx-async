"""Performance benchmarks for FrameBuffer._apply_canvas.

Baseline numbers (Phase 1) documented here for reference when comparing
against Phase 2 optimized results.

Run with:
    uv run pytest tests/benchmarks/test_framebuffer_perf.py -v -m benchmark -s
"""

from __future__ import annotations

import time

import pytest

from lifx.animation.framebuffer import FrameBuffer, TileRegion

TILE_WIDTH = 8
TILE_HEIGHT = 8
PIXELS_PER_TILE = TILE_WIDTH * TILE_HEIGHT
BENCHMARK_ITERATIONS = 1000


def _make_framebuffer(tile_count: int) -> FrameBuffer:
    """Create a FrameBuffer with N horizontally-arranged 8x8 tiles."""
    regions = [
        TileRegion(x=i * TILE_WIDTH, y=0, width=TILE_WIDTH, height=TILE_HEIGHT)
        for i in range(tile_count)
    ]
    return FrameBuffer(
        pixel_count=tile_count * PIXELS_PER_TILE,
        canvas_width=tile_count * TILE_WIDTH,
        canvas_height=TILE_HEIGHT,
        tile_regions=regions,
    )


def _make_canvas(tile_count: int) -> list[tuple[int, int, int, int]]:
    """Create a canvas of protocol-ready HSBK tuples for N tiles."""
    return [(32000, 65535, 65535, 3500)] * (tile_count * PIXELS_PER_TILE)


@pytest.mark.benchmark
def test_apply_canvas_1_tile() -> None:
    """Benchmark _apply_canvas for a 1-tile (64px) configuration.

    Phase 1 baseline: measures per-frame canvas extraction overhead for
    a single 8×8 tile without orientation remapping.
    """
    fb = _make_framebuffer(1)
    canvas = _make_canvas(1)

    start = time.perf_counter()
    for _ in range(BENCHMARK_ITERATIONS):
        fb.apply(canvas)
    elapsed = time.perf_counter() - start

    avg_ms = (elapsed / BENCHMARK_ITERATIONS) * 1000
    print(
        f"\n  1-tile _apply_canvas baseline: {avg_ms:.3f}ms avg ({BENCHMARK_ITERATIONS} iters)"
    )


@pytest.mark.benchmark
def test_apply_canvas_5_tile() -> None:
    """Benchmark _apply_canvas for a 5-tile (320px) configuration.

    Per spec PERF-H1: must complete in <5ms per call for this setup.
    This test establishes the Phase 1 baseline; Phase 2 LUT optimization
    should show a measurable improvement.

    Phase 1 baseline: nested-loop approach with per-frame index arithmetic
    across 5 tiles × 8 rows × 8 columns = 320 iterations.
    """
    fb = _make_framebuffer(5)
    canvas = _make_canvas(5)

    start = time.perf_counter()
    for _ in range(BENCHMARK_ITERATIONS):
        fb.apply(canvas)
    elapsed = time.perf_counter() - start

    avg_ms = (elapsed / BENCHMARK_ITERATIONS) * 1000
    print(
        f"\n  5-tile _apply_canvas baseline: {avg_ms:.3f}ms avg ({BENCHMARK_ITERATIONS} iters)"
    )

    assert avg_ms < 5.0, (
        f"_apply_canvas for 5-tile took {avg_ms:.3f}ms — exceeds 5ms target. "
        "Optimization required (see PERF-H1)."
    )


@pytest.mark.benchmark
def test_apply_canvas_10_tile() -> None:
    """Benchmark _apply_canvas for a 10-tile (640px) configuration.

    Phase 1 baseline: records per-frame cost for large multi-tile setups.
    10 tiles × 8 rows × 8 columns = 640 iterations per call.
    """
    fb = _make_framebuffer(10)
    canvas = _make_canvas(10)

    start = time.perf_counter()
    for _ in range(BENCHMARK_ITERATIONS):
        fb.apply(canvas)
    elapsed = time.perf_counter() - start

    avg_ms = (elapsed / BENCHMARK_ITERATIONS) * 1000
    print(
        f"\n  10-tile _apply_canvas baseline: {avg_ms:.3f}ms avg ({BENCHMARK_ITERATIONS} iters)"
    )
