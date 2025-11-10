"""Data models for the effects framework.

This module provides dataclasses for managing device state during effects.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from lifx.color import HSBK

if TYPE_CHECKING:
    from lifx.effects.base import LIFXEffect


@dataclass
class PreState:
    """Captured device state before an effect.

    Stores power state, color, and multizone colors to enable restoration
    after the effect completes.

    Attributes:
        power: Device power state (True=on, False=off)
        color: Current HSBK color (for non-multizone or overall color)
        zone_colors: List of zone colors for multizone devices (None for regular lights)

    Example:
        ```python
        # Captured state
        prestate = PreState(
            power=True,
            color=HSBK(hue=120, saturation=1.0, brightness=0.8, kelvin=3500),
            zone_colors=None,  # Not a multizone device
        )
        ```
    """

    power: bool
    color: HSBK
    zone_colors: list[HSBK] | None = None

    def __repr__(self) -> str:
        """String representation of PreState."""
        zones_info = (
            f"zones={len(self.zone_colors)}" if self.zone_colors else "no_zones"
        )
        return f"PreState(power={self.power}, color={self.color}, {zones_info})"


@dataclass
class RunningEffect:
    """Associates a running effect with its pre-state and background task.

    Tracks the effect instance, the device state captured before the
    effect started, and the background task running the effect.

    Attributes:
        effect: The running LIFXEffect instance
        prestate: Captured device state before effect
        task: Background asyncio task running the effect

    Example:
        ```python
        # Track running effect
        task = asyncio.create_task(effect.async_perform(lights))
        running = RunningEffect(effect=my_effect, prestate=captured_state, task=task)
        ```
    """

    effect: LIFXEffect
    prestate: PreState
    task: asyncio.Task[None]

    def __repr__(self) -> str:
        """String representation of RunningEffect."""
        effect_name = type(self.effect).__name__
        task_status = "running" if not self.task.done() else "done"
        return (
            f"RunningEffect(effect={effect_name}, "
            f"prestate={self.prestate}, task={task_status})"
        )
