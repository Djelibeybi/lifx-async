"""Light effects framework for lifx-async.

This module provides a comprehensive effects framework for creating and
managing visual effects on LIFX devices. It includes:

- Conductor: Central orchestrator for effect lifecycle management
- LIFXEffect: Abstract base class for custom effects
- EffectPulse: Pulse/blink/breathe effects with multiple modes
- EffectColorloop: Continuous hue rotation effects

Example:
    ```python
    from lifx import discover, DeviceGroup
    from lifx.effects import Conductor, EffectPulse, EffectColorloop

    # Discover devices
    devices = []
    async for device in discover():
        devices.append(device)
    group = DeviceGroup(devices)

    conductor = Conductor()

    # Pulse effect
    effect = EffectPulse(mode="blink", cycles=5)
    await conductor.start(effect, group.lights)

    # ColorLoop effect
    effect = EffectColorloop(period=30, change=20)
    await conductor.start(effect, group.lights)

    # Stop when done
    await conductor.stop(group.lights)
    ```
"""

from __future__ import annotations

from lifx.effects.aurora import EffectAurora
from lifx.effects.base import LIFXEffect
from lifx.effects.colorloop import EffectColorloop
from lifx.effects.conductor import Conductor
from lifx.effects.cylon import EffectCylon
from lifx.effects.double_slit import EffectDoubleSlit
from lifx.effects.embers import EffectEmbers
from lifx.effects.fireworks import EffectFireworks
from lifx.effects.flame import EffectFlame
from lifx.effects.frame_effect import FrameContext, FrameEffect
from lifx.effects.jacobs_ladder import EffectJacobsLadder
from lifx.effects.models import PreState, RunningEffect
from lifx.effects.newtons_cradle import EffectNewtonsCradle
from lifx.effects.pendulum_wave import EffectPendulumWave
from lifx.effects.plasma import EffectPlasma
from lifx.effects.plasma2d import EffectPlasma2D
from lifx.effects.progress import EffectProgress
from lifx.effects.pulse import EffectPulse
from lifx.effects.rainbow import EffectRainbow
from lifx.effects.registry import (
    DeviceSupport,
    DeviceType,
    EffectInfo,
    EffectRegistry,
    get_effect_registry,
)
from lifx.effects.ripple import EffectRipple
from lifx.effects.rule30 import EffectRule30
from lifx.effects.rule_trio import EffectRuleTrio
from lifx.effects.sine import EffectSine
from lifx.effects.sonar import EffectSonar
from lifx.effects.spectrum_sweep import EffectSpectrumSweep
from lifx.effects.spin import EffectSpin
from lifx.effects.state_manager import DeviceStateManager
from lifx.effects.sunrise import EffectSunrise, EffectSunset, SunOrigin
from lifx.effects.twinkle import EffectTwinkle
from lifx.effects.wave import EffectWave

__all__ = [
    "Conductor",
    "DeviceStateManager",
    "DeviceSupport",
    "DeviceType",
    "EffectAurora",
    "EffectColorloop",
    "EffectCylon",
    "EffectDoubleSlit",
    "EffectEmbers",
    "EffectFireworks",
    "EffectFlame",
    "EffectInfo",
    "EffectJacobsLadder",
    "EffectNewtonsCradle",
    "EffectPendulumWave",
    "EffectPlasma",
    "EffectPlasma2D",
    "EffectProgress",
    "EffectPulse",
    "EffectRainbow",
    "EffectRegistry",
    "EffectRipple",
    "EffectRule30",
    "EffectRuleTrio",
    "EffectSine",
    "EffectSonar",
    "EffectSpectrumSweep",
    "EffectSpin",
    "EffectSunrise",
    "EffectSunset",
    "EffectTwinkle",
    "EffectWave",
    "FrameContext",
    "FrameEffect",
    "LIFXEffect",
    "PreState",
    "RunningEffect",
    "SunOrigin",
    "get_effect_registry",
]
