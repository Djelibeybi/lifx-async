"""What Ceiling and Mirror lights offer the software effects package.

The Conductor and the effect state manager draw on light components, power
them on and restore them through these functions rather than reaching into a
light's internals. They are not part of the public device API.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lifx.animation.animator import AnimatorWriter
    from lifx.animation.framebuffer import FrameBuffer
    from lifx.color import HSBK
    from lifx.devices.component.light import ComponentMatrixLight
    from lifx.devices.component.participant import ComponentName


def component_positions(
    light: ComponentMatrixLight, component: ComponentName
) -> tuple[int, ...]:
    """Buffer positions of a light component, in its zone order."""
    return light._component_positions(component)


def other_component(
    light: ComponentMatrixLight, component: ComponentName
) -> ComponentName:
    """The light's other light component."""
    return light._other_component(component)


async def component_writer(
    light: ComponentMatrixLight,
    component: ComponentName,
    duration_ms: int,
    *,
    whole_light: bool = False,
    canvas: FrameBuffer | None = None,
) -> AnimatorWriter:
    """Borrow the light's Animator to draw on one light component's slot.

    Args:
        light: The light the light component belongs to
        component: The light component's name
        duration_ms: Transition duration for the writer's frames
        whole_light: True if the writer draws this light component's share
            of a whole-light effect
        canvas: The canvas a whole-light effect that moved onto this light
            component started with, or None for the light component's own

    Returns:
        A writer whose frames land on the light component's slot
    """
    return await light._component_writer(
        component, duration_ms, whole_light=whole_light, canvas=canvas
    )


async def power_on_component(
    light: ComponentMatrixLight, component: ComponentName, duration: float
) -> None:
    """Turn on only one light component of a light that is off."""
    await light._power_on_component(component, duration)


def stored_colors_snapshot(
    light: ComponentMatrixLight,
) -> dict[str, list[HSBK] | None] | None:
    """Copy both light components' stored colours, or None before state exists."""
    return light._stored_colors_snapshot()


async def reinstate_stored_colors(
    light: ComponentMatrixLight, snapshot: dict[str, list[HSBK] | None]
) -> None:
    """Put back stored colours copied before a whole-light software effect."""
    await light._reinstate_stored_colors(snapshot)


async def restore_component(
    light: ComponentMatrixLight,
    component: ComponentName,
    before: list[HSBK] | None,
    was_on: bool,
    stored: list[HSBK] | None,
) -> None:
    """Return one light component to its state before a software effect.

    Args:
        light: The light the light component belongs to
        component: The light component's name
        before: The whole tile, in buffer order, captured before the effect,
            or None if it could not be read
        was_on: Whether the light was on before the effect
        stored: The light component's stored colours before the effect
    """
    await light._restore_component(component, before, was_on, stored)
