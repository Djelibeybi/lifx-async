"""Light components as effect participants.

A Ceiling's uplight and downlight are light components: regions of one light
with their own colours and apparent on/off state. Each is also an effect
participant, so a software effect can draw on one light component while the
other stays under the caller's control through the light's existing component
methods.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lifx.animation.animator import Animator, AnimatorWriter
    from lifx.devices.component.light import ComponentMatrixLight
    from lifx.effects.base import LIFXEffect


class LightComponent:
    """One light component of a light, as an effect participant.

    Read it from the light, for example ``ceiling.downlight``. It carries
    only effect control: the light component's colours and power stay on the
    light's existing methods, such as ``set_uplight_color()``.

    Example:
        ```python
        from lifx.effects import EffectFlicker

        async with await Device.connect("192.168.1.100") as ceiling:
            await ceiling.downlight.start_effect(EffectFlicker())
            await ceiling.set_uplight_color(HSBK(30, 0.2, 0.3, 2700))
            await asyncio.sleep(10)
            await ceiling.downlight.stop_effect()
        ```
    """

    __slots__ = ("_light", "_name")

    def __init__(self, light: ComponentMatrixLight, name: str) -> None:
        """Name one light component of a light.

        Args:
            light: The light the light component belongs to
            name: The light component's name, such as ``"uplight"``
        """
        self._light = light
        self._name = name

    @property
    def animator(self) -> Animator:
        """The light's one Animator, which this light component draws through.

        A software effect on this light component writes its frames into the
        light component's slot on the light's Animator, which sends the tile
        composed from every slot.
        """
        return self._light.animator

    async def start_effect(self, effect: LIFXEffect) -> None:
        """Start a software effect on this light component alone.

        The effect draws on the light component's own shape: a Ceiling
        uplight is a single pixel, and a Ceiling downlight is the full grid
        with the uplight cell dropped. The other light component keeps its
        colours, and its colour and power methods keep working while the
        effect runs. On a light that is off, only this light component turns
        on and the other stays dark. Calling this light component's own
        colour or power methods stops the effect first.

        Args:
            effect: The software effect to run. It must draw frames: an
                effect such as EffectPulse, which sends waveforms to the
                whole light, cannot draw on a light component.

        Raises:
            TypeError: If ``effect`` does not draw frames
        """
        from lifx.effects.frame_effect import FrameEffect

        if not isinstance(effect, FrameEffect):
            raise TypeError(
                "A light component runs software effects that draw frames, "
                f"not {type(effect).__name__}"
            )
        await self._light._own_conductor().start(effect, [self])

    async def stop_effect(self) -> None:
        """Stop the software effect on this light component only.

        The light component gets its colours from before the effect back, or
        turns off again if it was dark or its light was off. An effect on the
        other light component, or on other lights in the same run, carries
        on.
        """
        from lifx.effects.conductor import Conductor

        await Conductor._leave_every_run(self)

    async def _writer(self, duration_ms: int) -> AnimatorWriter:
        """Borrow the light's Animator to draw on this light component's slot."""
        return await self._light._component_writer(self._name, duration_ms)

    def __repr__(self) -> str:
        """Name the light component and its light."""
        return f"LightComponent({self._name!r}, serial={self._light.serial!r})"
