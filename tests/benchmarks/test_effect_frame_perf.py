"""Performance benchmarks for effect frame generation.

Run with:
    uv run pytest tests/benchmarks/test_effect_frame_perf.py -v -m benchmark

Save a named baseline:
    uv run pytest tests/benchmarks/ -m benchmark --benchmark-save=phase1

Compare against a saved baseline:
    uv run pytest tests/benchmarks/ -m benchmark --benchmark-compare=phase1
"""

from __future__ import annotations

import pytest

from lifx.effects.aurora import EffectAurora
from lifx.effects.frame_effect import FrameContext


@pytest.mark.benchmark
def test_aurora_generate_frame_128px(benchmark) -> None:  # type: ignore[no-untyped-def]
    """Benchmark EffectAurora.generate_frame() for a 128-pixel device (16×8).

    LIFX Ceiling Capsule configuration. Measures HSBK object construction
    cost: 128 HSBK objects created per call. At 30 FPS: ~3,840 objects/sec
    per device. Phase 3 will add generate_protocol_frame() to bypass this
    (PERF-C1).
    """
    effect = EffectAurora()
    ctx = FrameContext(
        elapsed_s=1.0,
        device_index=0,
        pixel_count=128,
        canvas_width=16,
        canvas_height=8,
    )
    benchmark(effect.generate_frame, ctx)


@pytest.mark.benchmark
def test_aurora_generate_frame_320px(benchmark) -> None:  # type: ignore[no-untyped-def]
    """Benchmark EffectAurora.generate_frame() for a 5-tile canvas (5×8×8=320px).

    Multi-tile LIFX Tile setup. 320 HSBK objects created per call.
    At 30 FPS: ~9,600 objects/sec per device (PERF-C1).
    """
    effect = EffectAurora()
    ctx = FrameContext(
        elapsed_s=1.0,
        device_index=0,
        pixel_count=320,
        canvas_width=40,
        canvas_height=8,
    )
    benchmark(effect.generate_frame, ctx)


@pytest.mark.benchmark
def test_aurora_protocol_frame_128px(benchmark) -> None:  # type: ignore[no-untyped-def]
    """Benchmark EffectAurora.generate_protocol_frame() for 128px (16×8).

    Protocol-direct path bypassing HSBK object construction, validation,
    to_protocol() conversion, and LightHsbk allocation. Compare against
    test_aurora_generate_frame_128px to measure the overhead eliminated.
    """
    effect = EffectAurora()
    ctx = FrameContext(
        elapsed_s=1.0,
        device_index=0,
        pixel_count=128,
        canvas_width=16,
        canvas_height=8,
    )
    benchmark(effect.generate_protocol_frame, ctx)


@pytest.mark.benchmark
def test_aurora_protocol_frame_320px(benchmark) -> None:  # type: ignore[no-untyped-def]
    """Benchmark EffectAurora.generate_protocol_frame() for 320px (5×8×8).

    Protocol-direct path for multi-tile setup. Compare against
    test_aurora_generate_frame_320px to measure HSBK overhead eliminated.
    """
    effect = EffectAurora()
    ctx = FrameContext(
        elapsed_s=1.0,
        device_index=0,
        pixel_count=320,
        canvas_width=40,
        canvas_height=8,
    )
    benchmark(effect.generate_protocol_frame, ctx)
