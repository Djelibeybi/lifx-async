"""Overlap rules between whole-light and light component effects.

The newest instruction wins on a light. A whole-light effect replaces the
effects on its light components, and a light component effect takes its share
of a whole-light effect, which moves onto the other light component and stays
there. These rules hold across every live Conductor, so they live in a mixin
the Conductor inherits.
"""

from __future__ import annotations

import asyncio
import logging
import weakref
from collections.abc import Sequence
from typing import TYPE_CHECKING, ClassVar, cast

from lifx.devices.component.effect_support import (
    component_positions,
    component_writer,
    other_component,
)
from lifx.effects.frame_effect import (
    FrameEffect,
    borrowed_writers,
    drop_participant,
    rename_participant,
    replace_writer,
)
from lifx.effects.models import (
    ParticipantKey,
    PreState,
    RunningEffect,
    participant_key,
)
from lifx.effects.participants import Member, drawn_members, key_of, resolve

if TYPE_CHECKING:
    from lifx.devices.component.light import ComponentMatrixLight
    from lifx.devices.component.participant import ComponentName
    from lifx.devices.light import Light
    from lifx.effects.base import LIFXEffect
    from lifx.effects.participants import Participant

_LOGGER = logging.getLogger(__name__)

# For each whole light that took over light component effects: the light and
# each light component's original prior state.
TakenComponents = dict[
    ParticipantKey, tuple["ComponentMatrixLight", dict["ComponentName", PreState]]
]


def inherit_components(
    prestates: dict[ParticipantKey, PreState], components: TakenComponents
) -> None:
    """Give each whole light the original prior state of its light components.

    A whole-light effect that replaced light component effects captured a
    light still showing their frames. Each light component it took over
    gets its share of the tile and its stored colours from before its own
    effect started, and the light was on only if it was on before every one
    of them, so stopping the whole-light effect restores what was there
    before any effect started.

    Args:
        prestates: The prior state captured for each participant, updated
            in place
        components: For each whole light that took over light component
            effects, the light and each light component's original prior state
    """
    for key, (light, parts) in components.items():
        captured = prestates[key]
        owners = {
            position: prestate.tile_colors[0]
            for component, prestate in parts.items()
            if prestate.tile_colors
            for position in component_positions(light, component)
        }
        tile_colors = (
            [
                [
                    owners[position][position] if position in owners else colour
                    for position, colour in enumerate(captured.tile_colors[0])
                ],
                *captured.tile_colors[1:],
            ]
            if captured.tile_colors
            else None
        )
        stored = captured.stored_colors
        taken: dict[str, PreState] = {
            name: prestate for name, prestate in parts.items()
        }
        prestates[key] = PreState(
            power=captured.power and all(p.power for p in parts.values()),
            color=captured.color,
            zone_colors=captured.zone_colors,
            tile_colors=tile_colors,
            stored_colors=(
                {
                    name: (
                        (taken[name].stored_colors or {}).get(name)
                        if name in taken
                        else stored.get(name)
                    )
                    for name in stored
                }
                if stored is not None
                else None
            ),
        )


class OverlapRules:
    """The overlap rules, mixed into the Conductor.

    Every live Conductor is registered, so a light's effect is found and
    replaced whichever Conductor started it.
    """

    # Every live Conductor, so device.stop_effect() can find a run the light
    # is part of without the device holding a link to each Conductor.
    _live: ClassVar[weakref.WeakSet[OverlapRules]] = weakref.WeakSet()

    _running: dict[ParticipantKey, RunningEffect]
    _lock: asyncio.Lock

    async def remove_lights(
        self, lights: Sequence[Participant], restore_state: bool = True
    ) -> None:
        """Remove participants from their running effect; see Conductor."""
        raise NotImplementedError

    async def _remove(self, members: list[Member], *, restore_state: bool) -> None:
        """Remove each light or light component from its run; see Conductor."""
        raise NotImplementedError

    async def _restore(
        self, light: Light, component: ComponentName | None, prestate: PreState
    ) -> None:
        """Restore a whole light, or one light component; see Conductor."""
        raise NotImplementedError

    async def _take_over(
        self, effect: LIFXEffect, participants: Sequence[Participant]
    ) -> tuple[dict[ParticipantKey, PreState], TakenComponents]:
        """Stop the software effect each light already runs, on any Conductor.

        The light leaves its old run with no restore, so it never flashes back
        to its prior state; the old run's other participants carry on, and a
        run left with no participants is cancelled. The old run's prior state
        is always returned for the light, whatever the effects, so a later
        stop restores what was there before any effect rather than a frame
        captured mid-effect.

        The overlap rules for light components apply too. A whole light also
        takes over the effects on its light components, inheriting each
        light component's original prior state, which the caller merges into
        the state it captures. A light component takes its share of a
        whole-light effect, which moves onto the other light component, and
        inherits the whole light's original prior state.

        Args:
            effect: The effect about to start on the participants
            participants: The lights and light components it is about to
                start on

        Returns:
            The inherited prior state of each participant that has one, and
            for each whole light that took over light component effects, the
            light and each light component's original prior state
        """
        inherited: dict[ParticipantKey, PreState] = {}
        components: TakenComponents = {}
        loop = asyncio.get_running_loop()
        for participant in participants:
            key = key_of(participant)
            light, component = resolve(participant)
            for conductor in list(OverlapRules._live):
                # A run on another event loop cannot be cancelled from this one.
                if not conductor._runs_on(loop):
                    continue
                if component is None:
                    parts = await conductor._take_components(effect, light)
                    if parts:
                        _, merged = components.setdefault(
                            key, (cast("ComponentMatrixLight", light), {})
                        )
                        merged.update(parts)
                else:
                    whole = await conductor._take_share(
                        cast("ComponentMatrixLight", light), component
                    )
                    if whole is not None:
                        inherited[key] = whole
                running = conductor._running.get(key)
                if running is None or running.effect is effect:
                    continue
                inherited[key] = running.prestate
                _LOGGER.debug(
                    {
                        "class": self.__class__.__name__,
                        "method": "_take_over",
                        "action": "inherit_prestate",
                        "values": {
                            "participant": repr(participant),
                            "previous_effect": type(running.effect).__name__,
                            "new_effect": type(effect).__name__,
                        },
                    }
                )
                await conductor.remove_lights([participant], restore_state=False)
        return inherited, components

    def _runs_on(self, loop: asyncio.AbstractEventLoop) -> bool:
        """Whether every run on this Conductor belongs to ``loop``.

        Args:
            loop: The event loop the caller is running on

        Returns:
            True if no run here belongs to a different event loop
        """
        return all(run.task.get_loop() is loop for run in self._running.values())

    async def _take_components(
        self, effect: LIFXEffect, light: Light
    ) -> dict[ComponentName, PreState]:
        """Take a light's light components out of their runs here, unrestored.

        A whole-light effect started on a light replaces the effects on its
        light components, so the newest instruction wins. Each light
        component leaves its run with no restore in between.

        Args:
            effect: The whole-light effect about to start
            light: The light it is about to start on

        Returns:
            Each light component's original prior state, by name
        """
        parts: dict[ComponentName, PreState] = {
            key[1]: running.prestate
            for key, running in self._running.items()
            if isinstance(key, tuple)
            and key[0] == light.serial
            and running.effect is not effect
        }
        if parts:
            await self._remove(
                [(light, component) for component in parts], restore_state=False
            )
        return parts

    async def _take_share(
        self, light: ComponentMatrixLight, component: ComponentName
    ) -> PreState | None:
        """Take one light component's share of a whole-light effect here.

        A whole-light effect that draws frames moves onto the other light
        component. One that draws none, such as a waveform, cannot draw on a
        light component, so the light leaves it with no restore.

        Args:
            light: The light the light component belongs to
            component: The light component an effect is about to start on

        Returns:
            The whole light's original prior state, or None if no whole-light
            effect runs on the light here
        """
        running = self._running.get(light.serial)
        if running is None:
            return None
        if await self._move_whole_light(light, component) is None:
            await self._remove([(light, None)], restore_state=False)
        return running.prestate

    async def _move_whole_light(
        self, light: ComponentMatrixLight, leaving: ComponentName
    ) -> RunningEffect | None:
        """Move a whole-light effect off one light component, onto the other.

        The effect carries on with the same parameters and the whole light's
        original prior state, now as an effect on the other light component.
        It keeps the canvas it started with: on a Mirror it goes on drawing
        the other ring, and on a Ceiling it goes on drawing the full grid, of
        which only the other light component's cells reach the tile. It never
        expands back to the whole light.

        Args:
            light: The light running a whole-light effect here
            leaving: The light component the effect no longer draws on

        Returns:
            The moved run, or None if no whole-light effect that draws frames
            runs on the light here
        """
        async with self._lock:
            running = self._running.get(light.serial)
            if running is None or not isinstance(running.effect, FrameEffect):
                return None
            effect = running.effect
            other = other_component(light, leaving)
            writers = borrowed_writers(effect)
            matched = [
                idx
                for idx, member in enumerate(drawn_members(effect, effect.participants))
                if participant_key(*member) == light.serial
            ]
            for idx in reversed(matched):
                writer = writers[idx]
                if writer.component == leaving:
                    # A Mirror ring writer: the ring leaves the effect.
                    drop_participant(effect, idx)
                elif writer.component == other:
                    # The other Mirror ring now draws as a light component.
                    writer.leave_whole_light()
                else:
                    # A Ceiling draws the full grid onto the other light
                    # component's slot, on the canvas the effect started with.
                    replace_writer(
                        effect,
                        idx,
                        await component_writer(
                            light, other, writer.duration_ms, canvas=writer.canvas
                        ),
                    )
            # The writers drew as the whole light and now draw as the other
            # light component; their simulation carries on there, so a
            # Mirror's remaining ring keeps the frames and index both rings
            # shared.
            rename_participant(effect, light.serial, participant_key(light, other))
            del self._running[light.serial]
            self._running[participant_key(light, other)] = running
            _LOGGER.debug(
                {
                    "class": self.__class__.__name__,
                    "method": "_move_whole_light",
                    "action": "move",
                    "values": {
                        "serial": light.serial,
                        "component": other,
                        "effect": type(effect).__name__,
                    },
                }
            )
            return running

    @classmethod
    def _runs_whole_light(cls, light: Light) -> bool:
        """Whether a whole-light software effect runs on a light, on any Conductor."""
        return any(light.serial in conductor._running for conductor in cls._live)

    @classmethod
    async def _leave_every_run(
        cls, participant: Participant, *, restore_state: bool = True
    ) -> None:
        """Remove a participant from every run it is part of, on any Conductor.

        The participant's prior state is restored, unless ``restore_state`` is
        False, and the other participants of each run carry on. A whole light
        also leaves the runs of its light components. A light component also
        leaves a whole-light effect that draws frames on its light: the effect
        moves onto the other light component, and this light component gets
        the whole light's original prior state back. Runs are matched by
        participant key, so a second object for the same light finds them too.

        Args:
            participant: The light or light component leaving its runs
            restore_state: Whether to restore the participant's prior state
        """
        light, component = resolve(participant)
        for conductor in list(cls._live):
            if component is not None:
                moved = await conductor._move_whole_light(
                    cast("ComponentMatrixLight", light), component
                )
                if moved is not None and restore_state:
                    await conductor._restore(light, component, moved.prestate)
            found: list[Member] = [
                (light, key[1] if isinstance(key, tuple) else None)
                for key in conductor._running
                if key == key_of(participant)
                or (
                    component is None
                    and isinstance(key, tuple)
                    and key[0] == light.serial
                )
            ]
            if found:
                await conductor._remove(found, restore_state=restore_state)
