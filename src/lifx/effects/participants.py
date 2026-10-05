"""Effect participants: whole lights and light components.

A software effect draws on participants. A participant is a whole light, or
one light component of a Ceiling or Mirror, such as ``ceiling.downlight``.
These helpers resolve a participant to its light and light component, key it
for the Conductor, and line a frame effect's borrowed writers up with the
lights it draws on.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from lifx.devices.component.participant import ComponentName, LightComponent
from lifx.devices.mirror import MirrorLight
from lifx.effects.frame_effect import FrameEffect, borrowed_writers, writer_participant
from lifx.effects.models import ParticipantKey, participant_key

if TYPE_CHECKING:
    from lifx.devices.light import Light
    from lifx.effects.base import LIFXEffect

    # An effect participant: a whole light, or one light component of a light.
    Participant = Light | LightComponent

# A participant resolved to its light and light component (None for the
# whole light).
Member = tuple["Light", ComponentName | None]


def resolve(participant: Participant) -> Member:
    """Split an effect participant into its light and light component."""
    if isinstance(participant, LightComponent):
        return participant.light, participant.name
    return participant, None


def key_of(participant: Participant) -> ParticipantKey:
    """Return the Conductor key for an effect participant."""
    return participant_key(*resolve(participant))


def drawn_members(effect: LIFXEffect, lights: list[Light]) -> list[Member]:
    """Pair each light of an effect with the light component it takes part as.

    A frame effect's borrowed writers line up with its participants, and a
    light component's writer names its light component. A writer drawing a
    ring of a whole-light Mirror effect belongs to the whole light.
    """
    writers = borrowed_writers(effect) if isinstance(effect, FrameEffect) else []
    return [
        (light, writer_participant(writers[idx]) if idx < len(writers) else None)
        for idx, light in enumerate(lights)
    ]


def ring_names(participant: Participant) -> tuple[ComponentName, ...]:
    """The rings a whole-light effect draws on, one writer each.

    A whole-light effect on a Mirror runs as two ring participants, its front
    and back, so each ring is a canvas that wraps. Any other participant
    draws as itself.
    """
    if isinstance(participant, MirrorLight):
        return ("front", "back")
    return ()


def drawn_lights(
    effect: LIFXEffect, participants: Sequence[Participant]
) -> list[Light]:
    """The light of each participant, in writer order for a frame effect.

    A frame effect draws a whole-light Mirror once for each ring; any other
    effect takes part on the light once.
    """
    drawn = isinstance(effect, FrameEffect)
    return [
        light
        for participant in participants
        for light in [resolve(participant)[0]]
        * (max(len(ring_names(participant)), 1) if drawn else 1)
    ]
