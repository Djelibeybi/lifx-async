"""Performance benchmarks for MatrixPacketGenerator and MultiZonePacketGenerator.

Run with:
    uv run pytest tests/benchmarks/test_packets_perf.py -v -m benchmark

Save a named baseline:
    uv run pytest tests/benchmarks/ -m benchmark --benchmark-save=phase1

Compare against a saved baseline:
    uv run pytest tests/benchmarks/ -m benchmark --benchmark-compare=phase1
"""

from __future__ import annotations

import pytest

from lifx.animation.packets import MatrixPacketGenerator, MultiZonePacketGenerator

SOURCE = 12345
TARGET = b"\xd0\x73\x00\x00\x00\x01"


def _make_hsbk(count: int) -> list[tuple[int, int, int, int]]:
    """Create a list of protocol-ready HSBK tuples."""
    return [(32000, 65535, 65535, 3500)] * count


@pytest.mark.benchmark
def test_matrix_update_colors_64px(benchmark) -> None:  # type: ignore[no-untyped-def]
    """Benchmark MatrixPacketGenerator.update_colors for a 64px tile (8×8).

    Per-frame color flattening cost: 64 iterations building a 256-element
    flat list, then a single struct.pack_into call (PERF-H2).
    """
    gen = MatrixPacketGenerator(tile_count=1, tile_width=8, tile_height=8)
    templates = gen.create_templates(SOURCE, TARGET)
    hsbk = _make_hsbk(64)
    benchmark(gen.update_colors, templates, hsbk)


@pytest.mark.benchmark
def test_matrix_update_colors_128px(benchmark) -> None:  # type: ignore[no-untyped-def]
    """Benchmark MatrixPacketGenerator.update_colors for a 128px tile (16×8).

    LIFX Ceiling Capsule configuration. Large tile mode generates 3 templates:
    2× Set64 packets into the temp frame buffer + 1× CopyFrameBuffer to display.
    update_colors skips the CopyFrameBuffer packet (color_count == 0) and
    iterates over the 2 color-bearing templates × 64px each (PERF-H2).
    """
    gen = MatrixPacketGenerator(tile_count=1, tile_width=16, tile_height=8)
    templates = gen.create_templates(SOURCE, TARGET)
    hsbk = _make_hsbk(128)
    benchmark(gen.update_colors, templates, hsbk)


@pytest.mark.benchmark
def test_multizone_update_colors_82(benchmark) -> None:  # type: ignore[no-untyped-def]
    """Benchmark MultiZonePacketGenerator.update_colors for an 82-zone strip.

    Single SetExtendedColorZones packet: 82 iterations building a 328-element
    flat list before packing (PERF-H2).
    """
    gen = MultiZonePacketGenerator(zone_count=82)
    templates = gen.create_templates(SOURCE, TARGET)
    hsbk = _make_hsbk(82)
    benchmark(gen.update_colors, templates, hsbk)


@pytest.mark.benchmark
def test_multizone_update_colors_120(benchmark) -> None:  # type: ignore[no-untyped-def]
    """Benchmark MultiZonePacketGenerator.update_colors for a 120-zone strip.

    LIFX Neon configuration. Requires 2 SetExtendedColorZones packets
    (82 zones + 38 zones). Each packet flattens its zone slice independently
    before packing (PERF-H2).
    """
    gen = MultiZonePacketGenerator(zone_count=120)
    templates = gen.create_templates(SOURCE, TARGET)
    hsbk = _make_hsbk(120)
    benchmark(gen.update_colors, templates, hsbk)


@pytest.mark.benchmark
def test_matrix_create_templates_5_tile(benchmark) -> None:  # type: ignore[no-untyped-def]
    """Benchmark MatrixPacketGenerator.create_templates for a 5-tile device.

    One-time init-time cost. Establishing a baseline ensures Phase 2
    optimizations do not regress template creation.
    """
    gen = MatrixPacketGenerator(tile_count=5, tile_width=8, tile_height=8)
    benchmark(gen.create_templates, SOURCE, TARGET)
