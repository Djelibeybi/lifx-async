"""Performance benchmarks for effect frame generation.

Baseline numbers (Phase 1) documented here for reference when comparing
against Phase 3 optimized results (generate_protocol_frame path).

Run with:
    uv run pytest tests/benchmarks/test_effect_frame_perf.py -v -m benchmark -s
"""

from __future__ import annotations

import time

import pytest

from lifx.effects.aurora import EffectAurora
from lifx.effects.frame_effect import FrameContext

BENCHMARK_ITERATIONS = 500


@pytest.mark.benchmark
def test_aurora_generate_frame_128px() -> None:
    """Benchmark EffectAurora.generate_frame() for a 128-pixel device (16×8).

    Phase 1 baseline: measures HSBK object construction cost.
    At 30 FPS with 128 pixels: ~3,840 HSBK objects/second per device.

    Phase 3 will add generate_protocol_frame() returning raw uint16 tuples
    directly, bypassing HSBK construction entirely.
    """
    effect = EffectAurora()
    ctx = FrameContext(
        elapsed_s=1.0,
        device_index=0,
        pixel_count=128,
        canvas_width=16,
        canvas_height=8,
    )

    start = time.perf_counter()
    for _ in range(BENCHMARK_ITERATIONS):
        effect.generate_frame(ctx)
    elapsed = time.perf_counter() - start

    avg_ms = (elapsed / BENCHMARK_ITERATIONS) * 1000
    print(
        f"\n  aurora generate_frame 128px baseline: {avg_ms:.3f}ms avg ({BENCHMARK_ITERATIONS} iters)"
    )


@pytest.mark.benchmark
def test_aurora_generate_frame_320px() -> None:
    """Benchmark EffectAurora.generate_frame() for a 5-tile canvas (5×8×8=320px).

    Phase 1 baseline: canvas-scale generation for multi-tile LIFX Tile setup.
    At 30 FPS: ~9,600 HSBK objects/second per device.
    """
    effect = EffectAurora()
    ctx = FrameContext(
        elapsed_s=1.0,
        device_index=0,
        pixel_count=320,
        canvas_width=40,
        canvas_height=8,
    )

    start = time.perf_counter()
    for _ in range(BENCHMARK_ITERATIONS):
        effect.generate_frame(ctx)
    elapsed = time.perf_counter() - start

    avg_ms = (elapsed / BENCHMARK_ITERATIONS) * 1000
    print(
        f"\n  aurora generate_frame 320px baseline: {avg_ms:.3f}ms avg ({BENCHMARK_ITERATIONS} iters)"
    )
