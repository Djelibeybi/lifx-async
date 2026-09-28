"""Performance benchmarks for FrameBuffer._apply_canvas.

Run with:
    uv run pytest tests/benchmarks/test_framebuffer_perf.py -v -m benchmark

Save a named baseline:
    uv run pytest tests/benchmarks/ -m benchmark --benchmark-save=phase1

Compare against a saved baseline:
    uv run pytest tests/benchmarks/ -m benchmark --benchmark-compare=phase1
"""

from __future__ import annotations

import pytest

from lifx.animation.framebuffer import FrameBuffer, TileRegion

TILE_WIDTH = 8
TILE_HEIGHT = 8
PIXELS_PER_TILE = TILE_WIDTH * TILE_HEIGHT


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
def test_apply_canvas_1_tile(benchmark) -> None:  # type: ignore[no-untyped-def]
    """Benchmark _apply_canvas for a 1-tile (64px) configuration.

    Per-frame canvas extraction overhead for a single 8×8 tile without
    orientation remapping.
    """
    fb = _make_framebuffer(1)
    canvas = _make_canvas(1)
    benchmark(fb.apply, canvas)


@pytest.mark.benchmark
def test_apply_canvas_5_tile(benchmark) -> None:  # type: ignore[no-untyped-def]
    """Benchmark _apply_canvas for a 5-tile (320px) configuration.

    Must complete in under 5ms per call. Extraction uses a precomputed
    canvas-to-device lookup table so each frame only needs a single list
    comprehension over 320 indices (tiles × rows × cols), rather than
    per-frame index arithmetic.
    """
    fb = _make_framebuffer(5)
    canvas = _make_canvas(5)
    benchmark(fb.apply, canvas)


@pytest.mark.benchmark
def test_apply_canvas_10_tile(benchmark) -> None:  # type: ignore[no-untyped-def]
    """Benchmark _apply_canvas for a 10-tile (640px) configuration.

    Per-frame cost for large multi-tile setups (10 tiles × 8 rows × 8 cols
    = 640 lookup-table indices per call).
    """
    fb = _make_framebuffer(10)
    canvas = _make_canvas(10)
    benchmark(fb.apply, canvas)
