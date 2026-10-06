"""Seam audit: effects that already run on a Mirror ring are deliberate at zone 0.

A ring has no ends, so zone 24 sits next to zone 0. Each effect either closes
on itself there (the step from zone 24 to zone 0 is no bigger than any other
step) or is documented as keeping a seam. Every audited effect is seamless on
a wrapping canvas, and every effect draws a strip exactly as before when the
canvas does not wrap.
"""

from __future__ import annotations

import random

import pytest

from lifx.color import HSBK
from lifx.effects.aurora import EffectAurora
from lifx.effects.flicker import EffectFlicker
from lifx.effects.frame_effect import FrameEffect
from lifx.effects.sine import EffectSine
from lifx.effects.spectrum_sweep import EffectSpectrumSweep
from lifx.effects.twinkle import EffectTwinkle
from lifx.effects.wave import EffectWave
from tests.test_effects.test_ring_helpers import RING, advances_one_zone, ring_ctx

_TIMES = (0.0, 0.37, 1.1, 2.3, 3.9)


def _step(a: HSBK, b: HSBK) -> float:
    """Visible difference between neighbours, each channel scaled to 0..1."""
    hue_gap = abs(a.hue - b.hue) % 360
    hue_gap = min(hue_gap, 360 - hue_gap)
    return max(
        hue_gap / 180 * a.saturation,
        abs(a.saturation - b.saturation),
        abs(a.brightness - b.brightness),
    )


def _seam_excess(frame: list[HSBK]) -> float:
    """How much bigger the zone 24 to zone 0 step is than the steps beside it.

    A smooth pattern can change quickly in places, so the seam is held to the
    steps either side of it rather than to the steepest step on the ring.
    """
    steps = [_step(frame[i], frame[(i + 1) % RING]) for i in range(RING)]
    return steps[RING - 1] - 1.5 * max(steps[RING - 2], steps[0])


def _visibly_same(a: HSBK, b: HSBK) -> bool:
    return _step(a, b) < 0.01 and a.kelvin == b.kelvin


def _assert_seamless(effect: FrameEffect) -> None:
    for elapsed_s in _TIMES:
        frame = effect.generate_frame(ring_ctx(elapsed_s))
        assert _seam_excess(frame) <= 0.02, f"seam at t={elapsed_s}"


def test_wave_with_an_odd_node_count_has_no_seam_on_a_ring():
    _assert_seamless(EffectWave(nodes=3, drift=40.0))


def test_wave_keeps_its_node_count_on_a_ring_when_it_is_even():
    effect = EffectWave(nodes=2)
    frame = effect.generate_frame(ring_ctx(1.0))

    # Two nodes round the ring: the brightness dips twice, at the opposite
    # sides of the ring.
    dim = [i for i in range(RING) if frame[i].brightness < 0.4]
    assert dim and min(dim) < RING // 2 < max(dim)
    _assert_seamless(effect)


def _probe(frame: list[HSBK]) -> list[tuple[int, float, float, int]]:
    """Hue, saturation, brightness and kelvin of zones 0, 1, 12 and 24."""
    return [
        (round(frame[i].hue), frame[i].saturation, frame[i].brightness, frame[i].kelvin)
        for i in (0, 1, 12, RING - 1)
    ]


def _assert_strip_frame(frame: list[HSBK], expected: list[tuple]) -> None:
    for got, want in zip(_probe(frame), expected, strict=True):
        assert got[0] == pytest.approx(want[0], abs=1)
        assert got[1] == pytest.approx(want[1], abs=0.001)
        assert got[2] == pytest.approx(want[2], abs=0.001)
        assert got[3] == want[3]


def test_wave_on_a_strip_is_unchanged():
    frame = EffectWave(nodes=3, drift=40.0).generate_frame(ring_ctx(1.1, wraps=False))

    _assert_strip_frame(
        frame,
        [
            (239, 0.761, 0.624, 3500),
            (237, 0.919, 0.747, 3500),
            (352, 0.743, 0.638, 3500),
            (351, 0.730, 0.624, 3500),
        ],
    )


def test_sine_with_a_fractional_cycle_count_has_no_seam_on_a_ring():
    _assert_seamless(EffectSine(wavelength=0.7, hue2=300))


def test_sine_on_a_strip_is_unchanged():
    frame = EffectSine(wavelength=0.7, hue2=300).generate_frame(
        ring_ctx(1.1, wraps=False)
    )

    _assert_strip_frame(
        frame,
        [
            (200, 1.0, 0.02, 3500),
            (200, 1.0, 0.02, 3500),
            (264, 0.5, 0.447, 3500),
            (299, 0.87, 0.491, 3500),
        ],
    )


def test_spectrum_sweep_with_fractional_waves_has_no_seam_on_a_ring():
    # 1.5 waves cannot close on a ring, so the sweep holds two: a zone-time
    # later (speed * waves / zones) the pattern has moved exactly one zone.
    effect = EffectSpectrumSweep(speed=6.0, waves=1.5)
    before = effect.generate_frame(ring_ctx(1.0))
    after = effect.generate_frame(ring_ctx(1.0 + 6.0 * 2 / RING))

    assert advances_one_zone(before, after, 1, _visibly_same)


def test_spectrum_sweep_spaces_the_ring_evenly():
    frame = EffectSpectrumSweep().generate_frame(ring_ctx(0.0))

    # One wave round 25 zones: zone 0 is not repeated at zone 24.
    assert _step(frame[RING - 1], frame[0]) == pytest.approx(
        _step(frame[0], frame[1]), abs=0.05
    )


def test_spectrum_sweep_on_a_strip_is_unchanged():
    frame = EffectSpectrumSweep(waves=1.5).generate_frame(ring_ctx(1.1, wraps=False))

    _assert_strip_frame(
        frame,
        [
            (164, 1.0, 0.724, 3500),
            (148, 1.0, 0.789, 3500),
            (238, 0.836, 0.798, 3500),
            (347, 0.69, 0.765, 3500),
        ],
    )


def test_aurora_has_no_seam_on_a_ring():
    _assert_seamless(EffectAurora())


def test_aurora_protocol_frame_has_no_seam_on_a_ring():
    effect = EffectAurora()
    for elapsed_s in _TIMES:
        frame = effect.generate_protocol_frame(ring_ctx(elapsed_s))
        steps = [abs(frame[i][2] - frame[(i + 1) % RING][2]) for i in range(RING)]
        assert steps[RING - 1] <= max(steps[: RING - 1]) + 1300


def test_aurora_on_a_strip_is_unchanged():
    frame = EffectAurora().generate_frame(ring_ctx(1.1, wraps=False))

    _assert_strip_frame(
        frame,
        [
            (131, 0.802, 0.530, 3500),
            (139, 0.869, 0.660, 3500),
            (240, 0.635, 0.004, 3500),
            (123, 0.728, 0.419, 3500),
        ],
    )


def test_aurora_protocol_frame_on_a_strip_matches_its_frame():
    effect = EffectAurora()
    frame = effect.generate_frame(ring_ctx(1.1, wraps=False))
    protocol = effect.generate_protocol_frame(ring_ctx(1.1, wraps=False))

    assert [p[2] for p in protocol] == pytest.approx(
        [round(65535 * c.brightness) for c in frame], abs=2
    )


def test_flicker_has_no_seam_on_a_ring():
    # Flicker is noisy zone to zone, so compare the seam with the other steps
    # over many frames: it must be no rougher than any other pair of zones.
    effect = EffectFlicker()
    seam = other = 0.0
    frames = 80
    for n in range(frames):
        frame = effect.generate_frame(ring_ctx(n * 0.13))
        steps = [
            abs(frame[i].brightness - frame[(i + 1) % RING].brightness)
            for i in range(RING)
        ]
        seam += steps[RING - 1]
        other += sum(steps[: RING - 1]) / (RING - 1)

    assert seam / frames <= 1.25 * other / frames


def test_flicker_on_a_strip_is_unchanged():
    frame = EffectFlicker().generate_frame(ring_ctx(1.1, wraps=False))

    _assert_strip_frame(
        frame,
        [
            (20, 0.927, 0.514, 1989),
            (13, 0.953, 0.415, 1813),
            (16, 0.939, 0.467, 1905),
            (30, 0.889, 0.654, 2240),
        ],
    )


def _twinkle_frames(wraps: bool) -> list[list[HSBK]]:
    random.seed(7)
    effect = EffectTwinkle(density=1.0)
    return [
        effect.generate_frame(ring_ctx(0.05 * n, wraps=wraps)) for n in range(1, 40)
    ]


def test_twinkle_has_no_seam_because_its_zones_are_independent():
    # No zone looks at its neighbours, so the ring needs nothing special: a
    # wrapping canvas draws the same sparkles as a strip.
    assert _twinkle_frames(wraps=True) == _twinkle_frames(wraps=False)
    assert any(c.brightness > 0.5 for f in _twinkle_frames(True) for c in f)
