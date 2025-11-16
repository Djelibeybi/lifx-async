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

from lifx.effects.base import LIFXEffect
from lifx.effects.colorloop import EffectColorloop
from lifx.effects.conductor import Conductor
from lifx.effects.models import PreState, RunningEffect
from lifx.effects.pulse import EffectPulse
from lifx.effects.state_manager import DeviceStateManager

__all__ = [
    "Conductor",
    "DeviceStateManager",
    "LIFXEffect",
    "EffectPulse",
    "EffectColorloop",
    "PreState",
    "RunningEffect",
]
