"""The seam through which a light reaches its software effects.

Lights sit below the effects package: ``lifx.effects`` imports the device
classes, so a device cannot import the Conductor without an import cycle.
Instead the effects package registers an effect runner here when it is
imported, which importing ``lifx`` always does, and a light's
``start_effect()`` and ``stop_effect()``, and a Ceiling or Mirror's light
component methods, go through it.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, ClassVar, Protocol

if TYPE_CHECKING:
    from lifx.color import HSBK
    from lifx.devices.component.participant import LightComponent
    from lifx.devices.light import Light
    from lifx.effects.base import LIFXEffect


class EffectRunner(Protocol):
    """What a light asks of the software effects package."""

    async def start(
        self,
        participant: Light | LightComponent,
        effect: object,
        *,
        enable_thread: bool = False,
    ) -> None:
        """Start a software effect on one light or light component alone.

        Raises:
            TypeError: If ``effect`` is not a software effect the participant
                can run
            LifxUnsupportedCommandError: If the effect draws frames, the light
                is evidenced as Thread and ``enable_thread`` is False
        """
        ...

    async def leave_every_run(
        self, participant: Light | LightComponent, *, restore_state: bool = True
    ) -> None:
        """Remove a light or light component from every run it is part of."""
        ...

    def runs_whole_light(self, light: Light) -> bool:
        """Whether a whole-light software effect runs on a light."""
        ...

    def runs_mood_effect(self, light: Light) -> bool:
        """Whether a mood software effect runs on a whole light."""
        ...

    def scroll_effect(self, frame: list[list[HSBK]], vertical: bool) -> LIFXEffect:
        """The effect that scrolls a painted matrix mood."""
        ...

    def palette_effect(self, colors: list[HSBK]) -> LIFXEffect:
        """The effect that steps bulbs through a mood's colours."""
        ...

    async def start_together(self, lights: Sequence[Light], effect: object) -> None:
        """Start one software effect across several lights."""
        ...


class _Registry:
    """Holds the one effect runner the effects package registers."""

    runner: ClassVar[EffectRunner | None] = None


def register_effect_runner(runner: EffectRunner) -> None:
    """Register the effect runner lights use; called by ``lifx.effects``."""
    _Registry.runner = runner


def effect_runner() -> EffectRunner:
    """Return the registered effect runner.

    Raises:
        RuntimeError: If no effect runner has been registered
    """
    runner = _Registry.runner
    if runner is None:
        raise RuntimeError("Software effects need the lifx.effects package")
    return runner
