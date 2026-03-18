"""Performance benchmarks for MatrixPacketGenerator and MultiZonePacketGenerator.

Baseline numbers (Phase 1) documented here for reference when comparing
against Phase 2 optimized results.

Run with:
    uv run pytest tests/benchmarks/test_packets_perf.py -v -m benchmark -s
"""

from __future__ import annotations

import time

import pytest

from lifx.animation.packets import MatrixPacketGenerator, MultiZonePacketGenerator

BENCHMARK_ITERATIONS = 1000
SOURCE = 12345
TARGET = b"\xd0\x73\x00\x00\x00\x01"


def _make_hsbk(count: int) -> list[tuple[int, int, int, int]]:
    """Create a list of protocol-ready HSBK tuples."""
    return [(32000, 65535, 65535, 3500)] * count


@pytest.mark.benchmark
def test_matrix_update_colors_64px() -> None:
    """Benchmark MatrixPacketGenerator.update_colors for a 64px tile (8×8).

    Phase 1 baseline: per-frame color flattening cost using extend() loop.
    Each call: 64 iterations building a 256-element flat list, then struct.pack_into.
    """
    gen = MatrixPacketGenerator(tile_count=1, tile_width=8, tile_height=8)
    templates = gen.create_templates(SOURCE, TARGET)
    hsbk = _make_hsbk(64)

    start = time.perf_counter()
    for _ in range(BENCHMARK_ITERATIONS):
        gen.update_colors(templates, hsbk)
    elapsed = time.perf_counter() - start

    avg_us = (elapsed / BENCHMARK_ITERATIONS) * 1_000_000
    print(
        f"\n  update_colors 64px baseline: {avg_us:.1f}µs avg ({BENCHMARK_ITERATIONS} iters)"
    )


@pytest.mark.benchmark
def test_matrix_update_colors_128px() -> None:
    """Benchmark MatrixPacketGenerator.update_colors for a 128px tile (16×8).

    Phase 1 baseline: per-frame cost for Ceiling (16×8 = 128px, large tile mode).
    Multiple Set64 packets required — cost scales with packet count.
    """
    gen = MatrixPacketGenerator(tile_count=1, tile_width=16, tile_height=8)
    templates = gen.create_templates(SOURCE, TARGET)
    hsbk = _make_hsbk(128)

    start = time.perf_counter()
    for _ in range(BENCHMARK_ITERATIONS):
        gen.update_colors(templates, hsbk)
    elapsed = time.perf_counter() - start

    avg_us = (elapsed / BENCHMARK_ITERATIONS) * 1_000_000
    print(
        f"\n  update_colors 128px baseline: {avg_us:.1f}µs avg ({BENCHMARK_ITERATIONS} iters)"
    )


@pytest.mark.benchmark
def test_multizone_update_colors_82() -> None:
    """Benchmark MultiZonePacketGenerator.update_colors for an 82-zone strip.

    Phase 1 baseline: per-frame cost for a single SetExtendedColorZones packet.
    82 iterations building a 328-element flat list before packing.
    """
    gen = MultiZonePacketGenerator(zone_count=82)
    templates = gen.create_templates(SOURCE, TARGET)
    hsbk = _make_hsbk(82)

    start = time.perf_counter()
    for _ in range(BENCHMARK_ITERATIONS):
        gen.update_colors(templates, hsbk)
    elapsed = time.perf_counter() - start

    avg_us = (elapsed / BENCHMARK_ITERATIONS) * 1_000_000
    print(
        f"\n  multizone update_colors 82z baseline: {avg_us:.1f}µs avg ({BENCHMARK_ITERATIONS} iters)"
    )


@pytest.mark.benchmark
def test_matrix_create_templates_5_tile() -> None:
    """Benchmark MatrixPacketGenerator.create_templates for a 5-tile device.

    Records template creation cost. This is a one-time init-time cost,
    not a per-frame cost, but establishing baseline confirms optimization
    does not regress template creation.
    """
    start = time.perf_counter()
    for _ in range(BENCHMARK_ITERATIONS):
        gen = MatrixPacketGenerator(tile_count=5, tile_width=8, tile_height=8)
        gen.create_templates(SOURCE, TARGET)
    elapsed = time.perf_counter() - start

    avg_us = (elapsed / BENCHMARK_ITERATIONS) * 1_000_000
    print(
        f"\n  create_templates 5-tile baseline: {avg_us:.1f}µs avg ({BENCHMARK_ITERATIONS} iters)"
    )
