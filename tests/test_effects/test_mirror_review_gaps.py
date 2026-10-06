"""Mirror ring behaviour that only shows up in a run or across participants.

Three seams:

* a Conductor run on the emulator that mixes a Mirror ring and a strip, where
  ``seamless=True`` must fold the ring and leave the strip alone;
* a Conductor start of plasma or embers on a matrix light that is not a
  Mirror, which must be refused;
* a ring and a strip drawn as separate participants of one effect, which must
  not share simulation state.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Callable

import pytest

from lifx.devices.mirror import MirrorLight
from lifx.devices.multizone import MultiZoneLight
from lifx.effects import (
    EffectDoubleSlit,
    EffectEmbers,
    EffectFireworks,
    EffectJacobsLadder,
    EffectPendulumWave,
    EffectPlasma,
    EffectRule30,
    EffectRuleTrio,
    EffectSonar,
)
from lifx.effects.conductor import Conductor
from lifx.effects.frame_effect import FrameContext, FrameEffect
from tests.test_effects.test_ring_helpers import RING, as_tuples, ring_ctx


def _recording(cls: type[FrameEffect]) -> type[FrameEffect]:
    """The effect class, recording every context it draws and the frame."""

    class Recording(cls):  # type: ignore[valid-type, misc]
        def __init__(self, **kwargs) -> None:
            super().__init__(**kwargs)
            self.drawn: list[tuple[FrameContext, list]] = []

        def generate_frame(self, ctx: FrameContext) -> list:
            frame = super().generate_frame(ctx)
            self.drawn.append((ctx, frame))
            return frame

    return Recording


async def _until(check: Callable[[], bool]) -> None:
    for _ in range(100):
        if check():
            return
        await asyncio.sleep(0.05)
    raise AssertionError("the run never drew the frames it should")


@pytest.mark.emulator
@pytest.mark.parametrize("cls", [EffectPendulumWave, EffectDoubleSlit])
class TestSeamlessFoldsOnlyTheRing:
    async def test_a_conductor_run_folds_the_ring_and_leaves_the_strip(
        self, mirror_device, emulator_devices, cls
    ):
        mirror = mirror_device
        strip = emulator_devices[4]
        assert isinstance(mirror, MirrorLight)
        assert isinstance(strip, MultiZoneLight)
        async with mirror:
            effect = _recording(cls)(seamless=True)
            conductor = Conductor()
            await conductor.start(effect, [mirror.front, strip])
            try:
                await _until(
                    lambda: {c.wraps for c, _ in effect.drawn} == {True, False}
                )
            finally:
                await conductor.stop([mirror.front, strip])

        rings = [(c, f) for c, f in effect.drawn if c.wraps]
        strips = [(c, f) for c, f in effect.drawn if not c.wraps]
        for ctx, frame in rings:
            tuples = as_tuples(frame)
            assert len(tuples) == RING
            assert len(set(tuples)) > 1
            for i in range(1, RING):
                assert tuples[i] == tuples[RING - i]
        for ctx, frame in strips:
            unfolded = cls(seamless=False).generate_frame(ctx)
            assert as_tuples(frame) == as_tuples(unfolded)


@pytest.mark.emulator
@pytest.mark.parametrize("cls", [EffectPlasma, EffectEmbers])
class TestPlasmaAndEmbersRefuseOtherMatrixLights:
    async def test_a_conductor_refuses_a_tile(self, emulator_devices, cls):
        tile = emulator_devices[6]
        async with tile:
            conductor = Conductor()
            await conductor.start(cls(), [tile])
            try:
                assert conductor.effect(tile) is None
            finally:
                await conductor.stop([tile])

    async def test_a_conductor_refuses_a_ceiling(self, ceiling_device, cls):
        ceiling = ceiling_device
        async with ceiling:
            conductor = Conductor()
            await conductor.start(cls(), [ceiling])
            try:
                assert conductor.effect(ceiling) is None
            finally:
                await conductor.stop([ceiling])


_STATEFUL: dict[str, Callable[[], FrameEffect]] = {
    "fireworks": lambda: EffectFireworks(launch_rate=2.0, burst_spread=20.0),
    "plasma": lambda: EffectPlasma(tendril_rate=2.0),
    "embers": lambda: EffectEmbers(),
    "rule30": lambda: EffectRule30(seed="random", speed=5.0),
    "rule_trio": lambda: EffectRuleTrio(speed=5.0),
    "sonar": lambda: EffectSonar(),
    "jacobs_ladder": lambda: EffectJacobsLadder(),
}

_FRAMES = 120


def _solo(factory: Callable[[], FrameEffect], wraps: bool, parity: int) -> list:
    """Frames the effect draws for one canvas kind, with nothing else drawn."""
    effect = factory()
    out = []
    for f in range(_FRAMES):
        random.seed(2 * f + parity)
        out.append(as_tuples(effect.generate_frame(ring_ctx(f / 20, wraps))))
    return out


@pytest.mark.parametrize("name", _STATEFUL)
class TestARingAndAStripDoNotShareState:
    """Each participant keeps its own simulation, so drawing one never moves the other.

    Every draw is seeded from its frame, so the random choices the effect makes
    are the same whether or not the other participant draws as well.
    """

    def test_a_ring_and_a_strip_of_one_length_draw_as_they_do_alone(
        self, name: str
    ) -> None:
        factory = _STATEFUL[name]
        effect = factory()
        ring: list = []
        strip: list = []
        for f in range(_FRAMES):
            for key, wraps, parity, out in (
                ("ring", True, 0, ring),
                ("strip", False, 1, strip),
            ):
                effect._draw_as(key, ["ring", "strip"])
                random.seed(2 * f + parity)
                out.append(as_tuples(effect.generate_frame(ring_ctx(f / 20, wraps))))
        assert ring == _solo(factory, wraps=True, parity=0)
        assert strip == _solo(factory, wraps=False, parity=1)
