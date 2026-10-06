"""Conductor orchestrator for managing light effects.

This module provides the Conductor class that coordinates effect lifecycle
across multiple devices.
"""

from __future__ import annotations

import asyncio
import logging
import weakref
from collections.abc import Sequence
from typing import TYPE_CHECKING, cast

from lifx.animation.animator import AnimatorWriter
from lifx.color import HSBK
from lifx.devices.component.effect_support import (
    component_writer,
    power_on_component,
)
from lifx.devices.component.participant import LightComponent
from lifx.devices.effect_runner import register_effect_runner
from lifx.effects.base import LIFXEffect
from lifx.effects.const import POWER_ON_TRANSITION_DURATION
from lifx.effects.frame_effect import (
    FrameEffect,
    add_writers,
    drop_participant,
    last_frame,
    lend_writers,
)
from lifx.effects.models import (
    ParticipantKey,
    PreState,
    RunningEffect,
    participant_key,
)
from lifx.effects.overlap import OverlapRules, TakenComponents, inherit_components
from lifx.effects.participants import (
    Member,
    drawn_lights,
    drawn_members,
    key_of,
    resolve,
    ring_names,
)
from lifx.effects.state_manager import DeviceStateManager

if TYPE_CHECKING:
    from lifx.devices.component.light import ComponentMatrixLight
    from lifx.devices.component.participant import ComponentName
    from lifx.devices.light import Light
    from lifx.effects.participants import Participant

_LOGGER = logging.getLogger(__name__)


class Conductor(OverlapRules):
    """Central orchestrator for managing light effects across multiple devices.

    The Conductor manages the complete lifecycle of effects: capturing device
    state before effects, executing effects, and restoring state afterward.
    All effect execution is coordinated through the conductor.

    Attributes:
        _running: Dictionary mapping effect participant key to RunningEffect
        _lock: Asyncio lock for thread-safe state management

    Example:
        ```python
        conductor = Conductor()

        # Start an effect
        effect = EffectPulse(mode="blink", cycles=5)
        await conductor.start(effect, [light1, light2])

        # Check running effect
        current = conductor.effect(light1)
        if current:
            print(f"Running: {type(current).__name__}")

        # Stop effects
        await conductor.stop([light1, light2])
        ```
    """

    def __init__(self) -> None:
        """Initialize the Conductor."""
        self._state_manager = DeviceStateManager()
        self._running: dict[ParticipantKey, RunningEffect] = {}
        self._lock = asyncio.Lock()
        OverlapRules._live.add(self)

    def effect(self, light: Participant) -> LIFXEffect | None:
        """Return the effect currently running on a participant, or None if idle.

        Args:
            light: The light or light component to check

        Returns:
            Currently running LIFXEffect instance, or None

        Example:
            ```python
            current_effect = conductor.effect(light)
            if current_effect:
                print(f"Running: {type(current_effect).__name__}")
            ```
        """
        running = self._running.get(key_of(light))
        return running.effect if running else None

    def get_last_frame(self, light: Participant) -> list[HSBK] | None:
        """Return the most recent HSBK frame sent to a device, or None.

        For frame-based effects, returns the list of HSBK colors from the
        most recent call to generate_frame() for this device. Returns None
        if no effect is running on the device, the effect is not frame-based,
        no frame has been generated yet, or the effect overrides
        generate_protocol_frame() directly (bypassing HSBK construction).

        Args:
            light: The light or light component to query

        Returns:
            List of HSBK colors from the last frame, or None

        Example:
            ```python
            frame = conductor.get_last_frame(light)
            if frame:
                avg_brightness = sum(c.brightness for c in frame) / len(frame)
                print(f"Average brightness: {avg_brightness:.1%}")
            ```
        """
        key = key_of(light)
        running = self._running.get(key)
        if not running:
            return None

        effect = running.effect
        if not isinstance(effect, FrameEffect):
            return None
        frame = last_frame(effect, key)
        rings = ring_names(light)
        if frame is None and rings:
            # A whole-light Mirror effect draws each ring through a writer:
            # its frame is every ring's frame in turn, as the effect drew it.
            frames = [
                last_frame(effect, participant_key(cast("Light", light), ring))
                for ring in rings
            ]
            whole: list[HSBK] = []
            for ring_frame in frames:
                if ring_frame is None:
                    return None
                whole.extend(ring_frame)
            return whole
        return frame

    async def start(
        self,
        effect: LIFXEffect,
        participants: Sequence[Participant],
        *,
        enable_thread: bool = False,
    ) -> None:
        """Start an effect on one or more lights or light components.

        Captures current light state, powers on if needed, and launches
        the effect. State is automatically restored when effect completes
        or stop() is called.

        A light component, such as ``ceiling.downlight``, takes part only in
        effects that draw frames; any other effect leaves it out. A whole
        light replaces the effects on its light components and inherits each
        one's original prior state; a light component moves a whole-light
        effect on its light onto the other light component.

        An effect that draws frames streams them to every participant, and
        a Thread mesh is not built for that traffic. If any participant's
        light is evidenced as Thread, by its own replies or an mDNS record,
        the whole start is refused before anything is captured or changed,
        unless ``enable_thread`` is True. A light not yet heard from is not
        refused. An effect that streams no frames, such as EffectPulse or
        EffectColorloop, is never refused.

        Args:
            effect: The effect instance to execute
            participants: Lights and light components to apply effect to
            enable_thread: Stream frames to lights evidenced as Thread
                anyway. Off by default.

        Raises:
            LifxTimeoutError: If light state capture times out
            LifxDeviceNotFoundError: If light becomes unreachable
            LifxUnsupportedCommandError: If the effect draws frames, a
                participant's light is evidenced as Thread and
                ``enable_thread`` is False

        Example:
            ```python
            # Start pulse effect on all lights
            effect = EffectPulse(mode="breathe", cycles=3)
            await conductor.start(effect, group.lights)
            ```
        """
        _refuse_thread_frames(
            effect, participants, "Conductor.start()", enable_thread=enable_thread
        )

        # Filter participants based on effect requirements
        filtered_participants = await self._filter_compatible_lights(
            effect, participants
        )

        if not filtered_participants:
            _LOGGER.warning(
                {
                    "class": self.__class__.__name__,
                    "method": "start",
                    "action": "filter",
                    "values": {
                        "effect": type(effect).__name__,
                        "total_participants": len(participants),
                        "compatible_participants": 0,
                    },
                }
            )
            return

        # Newest wins: stop whatever each participant already runs, with no
        # restore in between, before this effect captures or inherits.
        inherited, components = await self._take_over(effect, filtered_participants)

        async with self._lock:
            # Set conductor reference in effect
            effect.conductor = self
            members = [resolve(p) for p in filtered_participants]
            lights = [light for light, _ in members]

            # Capture prestates in parallel for participants that inherit none
            prestates: dict[ParticipantKey, PreState] = {}
            to_capture: list[tuple[ParticipantKey, Light]] = []
            for light, component in members:
                key = participant_key(light, component)
                if key in inherited:
                    prestates[key] = inherited[key]
                else:
                    to_capture.append((key, light))

            if to_capture:

                async def capture_and_log(device: Light) -> PreState:
                    prestate = await self._state_manager.capture_state(device)
                    _LOGGER.debug(
                        {
                            "class": self.__class__.__name__,
                            "method": "start",
                            "action": "capture",
                            "values": {
                                "serial": device.serial,
                                "power": prestate.power,
                                "color": {
                                    "hue": prestate.color.hue,
                                    "saturation": prestate.color.saturation,
                                    "brightness": prestate.color.brightness,
                                    "kelvin": prestate.color.kelvin,
                                },
                                "has_zones": prestate.zone_colors is not None,
                            },
                        }
                    )
                    return prestate

                captured = await asyncio.gather(
                    *(capture_and_log(light) for _, light in to_capture)
                )
                prestates.update(zip((key for key, _ in to_capture), captured))
            inherit_components(prestates, components)

            # Set up animators for frame-based effects
            if isinstance(effect, FrameEffect):
                # Set participants early so async_setup() can access them
                # (async_perform() sets this too but runs in a background task).
                # A whole-light Mirror draws through a writer for each ring,
                # but setup sees each participant once, in index order.
                setup = lights
                lights = drawn_lights(effect, filtered_participants)
                effect.participants = lights
                await self._power_on_components(effect, filtered_participants)
                animators = await self._create_animators(effect, filtered_participants)
                lend_writers(effect, animators)
                await effect.async_setup(setup)

            # Create background task for the effect
            task = asyncio.create_task(self._run_effect_with_cleanup(effect, lights))

            # Register running effects for all participants
            for light, component in members:
                key = participant_key(light, component)
                self._running[key] = RunningEffect(
                    effect=effect,
                    prestate=prestates[key],
                    task=task,
                )

    async def stop(self, lights: Sequence[Participant]) -> None:
        """Stop effects and restore light state.

        Halts any running effects on the specified lights or light
        components and restores them to their pre-effect state (power,
        colour, zones). A light also stops the effects on its light
        components in this Conductor, including a whole-light effect that
        moved onto one; a light component stops only its own effect. Any
        other participants of the same run carry on: the run ends only when
        its last participant stops.

        Args:
            lights: Lights and light components to stop

        Example:
            ```python
            # Stop all lights
            await conductor.stop(group.lights)

            # Stop specific lights
            await conductor.stop([light1, light2])
            ```
        """
        await self._remove(self._members_of(lights), restore_state=True)

    def _members_of(self, participants: Sequence[Participant]) -> list[Member]:
        """Each participant, and for a whole light its light components here.

        Stopping or removing a light covers every effect on it in this
        Conductor, including one on either light component, such as a
        whole-light effect that moved onto one. A light component covers only
        itself.

        Args:
            participants: The lights and light components to stop or remove

        Returns:
            Each light and light component to stop or remove
        """
        members: list[Member] = []
        for participant in participants:
            light, component = resolve(participant)
            members.append((light, component))
            if component is None:
                members.extend(
                    (light, key[1])
                    for key in self._running
                    if isinstance(key, tuple) and key[0] == light.serial
                )
        return members

    async def add_lights(
        self,
        effect: LIFXEffect,
        lights: Sequence[Participant],
        *,
        enable_thread: bool = False,
    ) -> None:
        """Add lights or light components to a running effect without restarting it.

        Captures state, creates animators (for FrameEffects), and registers
        them as participants of the already-running effect. Participants
        that are already running this effect or are incompatible are skipped.

        As in ``start()``, a light evidenced as Thread refuses the whole
        addition of a frame-drawing effect, before anything is captured or
        changed, unless ``enable_thread`` is True.

        Args:
            effect: The effect to add participants to (must already be running)
            lights: Lights and light components to add
            enable_thread: Stream frames to lights evidenced as Thread
                anyway. Off by default.

        Raises:
            LifxUnsupportedCommandError: If the effect draws frames, a light
                is evidenced as Thread and ``enable_thread`` is False

        Example:
            ```python
            # Add a new light to an already-running effect
            await conductor.add_lights(effect, [new_light])
            ```
        """
        _refuse_thread_frames(
            effect, lights, "Conductor.add_lights()", enable_thread=enable_thread
        )

        # Filter compatible lights
        compatible = await self._filter_compatible_lights(effect, lights)
        if not compatible:
            return

        # Newest wins, as in start(): a light running another effect leaves
        # that run with no restore in between. An effect that is not running
        # here takes no light from anywhere.
        inherited: dict[ParticipantKey, PreState] = {}
        components: TakenComponents = {}
        if any(running.effect is effect for running in self._running.values()):
            inherited, components = await self._take_over(effect, compatible)

        async with self._lock:
            # Skip participants already running this effect
            new_participants: list[Participant] = []
            for participant in compatible:
                running = self._running.get(key_of(participant))
                if running and running.effect is effect:
                    continue
                new_participants.append(participant)

            if not new_participants:
                return

            # Find the task reference from existing participants
            task: asyncio.Task[None] | None = None
            for running in self._running.values():
                if running.effect is effect:
                    task = running.task
                    break

            if task is None:
                _LOGGER.warning(
                    {
                        "class": self.__class__.__name__,
                        "method": "add_lights",
                        "action": "no_task",
                        "values": {
                            "effect": type(effect).__name__,
                            "lights": len(new_participants),
                        },
                    }
                )
                return

            # Capture prestates in parallel for participants inheriting none
            to_capture = [p for p in new_participants if key_of(p) not in inherited]
            captured = await asyncio.gather(
                *(self._state_manager.capture_state(resolve(p)[0]) for p in to_capture)
            )
            prestates = dict(inherited)
            prestates.update(zip([key_of(p) for p in to_capture], captured))
            inherit_components(prestates, components)

            # Create animators for frame-based effects
            if isinstance(effect, FrameEffect):
                await self._power_on_components(effect, new_participants)
                new_animators = await self._create_animators(effect, new_participants)
                add_writers(effect, new_animators)

            # Add to participants, a whole-light Mirror once for each ring
            effect.participants.extend(drawn_lights(effect, new_participants))

            # Register in running map
            for participant in new_participants:
                key = key_of(participant)
                self._running[key] = RunningEffect(
                    effect=effect,
                    prestate=prestates[key],
                    task=task,
                )

            _LOGGER.debug(
                {
                    "class": self.__class__.__name__,
                    "method": "add_lights",
                    "action": "added",
                    "values": {
                        "effect": type(effect).__name__,
                        "added_count": len(new_participants),
                    },
                }
            )

    async def remove_lights(
        self, lights: Sequence[Participant], restore_state: bool = True
    ) -> None:
        """Remove participants from their running effect without stopping others.

        Closes animators, optionally restores state, and deregisters the
        lights or light components. A light also leaves the effects on its
        light components in this Conductor. If the last participant is
        removed, cancels the background task.

        Args:
            lights: Lights and light components to remove
            restore_state: Whether to restore pre-effect state (default True)

        Example:
            ```python
            # Remove a light and restore its state
            await conductor.remove_lights([light1])

            # Remove without restoring state
            await conductor.remove_lights([light2], restore_state=False)
            ```
        """
        await self._remove(self._members_of(lights), restore_state=restore_state)

    async def _remove(self, members: list[Member], *, restore_state: bool) -> None:
        """Remove each light or light component from its run; see remove_lights()."""
        tasks_to_cancel: set[asyncio.Task[None]] = set()
        to_restore: list[tuple[Light, ComponentName | None, PreState]] = []

        async with self._lock:
            for light, component in members:
                key = participant_key(light, component)
                running = self._running.get(key)
                if not running:
                    continue

                effect = running.effect

                # Drop the participant and, for frame effects, its writers:
                # a whole-light Mirror draws through one for each ring
                matched = [
                    idx
                    for idx, member in enumerate(
                        drawn_members(effect, effect.participants)
                    )
                    if participant_key(*member) == key
                ]
                for idx in reversed(matched):
                    if isinstance(effect, FrameEffect):
                        drop_participant(effect, idx)
                    else:
                        del effect.participants[idx]

                # Track for restoration
                if restore_state:
                    to_restore.append((light, component, running.prestate))

                # Check if this was the last participant
                remaining = sum(
                    1
                    for r in self._running.values()
                    if r.task is running.task and r.effect is effect
                )
                # Count will include current light (not yet removed from _running)
                if remaining <= 1:
                    tasks_to_cancel.add(running.task)

                del self._running[key]

                _LOGGER.debug(
                    {
                        "class": self.__class__.__name__,
                        "method": "remove_lights",
                        "action": "removed",
                        "values": {
                            "serial": light.serial,
                            "component": component,
                            "effect": type(effect).__name__,
                            "restore_state": restore_state,
                        },
                    }
                )

        # Cancel orphaned tasks (outside lock)
        for task in tasks_to_cancel:
            if not task.done():
                task.cancel()
        if tasks_to_cancel:
            await asyncio.gather(*tasks_to_cancel, return_exceptions=True)

        # Restore state (outside lock)
        if to_restore:
            await asyncio.gather(*(self._restore(*item) for item in to_restore))

    async def _restore(
        self, light: Light, component: ComponentName | None, prestate: PreState
    ) -> None:
        """Restore a whole light, or one light component of it."""
        if component is None:
            await self._state_manager.restore_state(light, prestate)
        else:
            await self._state_manager.restore_component(
                cast("ComponentMatrixLight", light), component, prestate
            )

    async def _run_effect_with_cleanup(
        self, effect: LIFXEffect, participants: list[Light]
    ) -> None:
        """Run effect and handle cleanup on completion or error.

        Args:
            effect: The effect to run
            participants: List of lights participating in the effect
        """
        try:
            # Run the effect
            await effect.async_perform(participants)

            # Close animators for frame effects, once each writer has said
            # which light component its light draws on
            members = drawn_members(effect, participants)
            if isinstance(effect, FrameEffect):
                effect.close_animators()

            # Effect completed successfully - restore state
            _LOGGER.debug(
                {
                    "class": self.__class__.__name__,
                    "method": "_run_effect_with_cleanup",
                    "action": "complete",
                    "values": {
                        "effect": type(effect).__name__,
                        "participant_count": len(participants),
                    },
                }
            )
            async with self._lock:
                # Only restore state if the effect wants it
                if effect.restore_on_complete:
                    # A whole-light Mirror appears once for each ring, and is
                    # restored once.
                    to_restore: dict[
                        ParticipantKey, tuple[Light, ComponentName | None, PreState]
                    ] = {}
                    for light, component in members:
                        key = participant_key(light, component)
                        running = self._running.get(key)
                        if running:
                            to_restore[key] = (light, component, running.prestate)

                    # Restore all participants in parallel
                    if to_restore:
                        await asyncio.gather(
                            *(self._restore(*item) for item in to_restore.values())
                        )

                # Remove from running registry
                for member in members:
                    self._running.pop(participant_key(*member), None)

        except asyncio.CancelledError:
            # Effect was cancelled via stop() - this is expected
            _LOGGER.debug(
                {
                    "class": self.__class__.__name__,
                    "method": "_run_effect_with_cleanup",
                    "action": "cancel",
                    "values": {
                        "effect": type(effect).__name__,
                        "participant_count": len(participants),
                    },
                }
            )
            raise  # Re-raise so task.cancel() completes
        except Exception as e:
            # Unexpected error during effect execution
            _LOGGER.error(
                {
                    "class": self.__class__.__name__,
                    "method": "_run_effect_with_cleanup",
                    "action": "error",
                    "error": str(e),
                    "values": {
                        "effect": type(effect).__name__,
                        "participant_count": len(participants),
                    },
                },
                exc_info=True,
            )
            # Close animators for frame effects
            members = drawn_members(effect, participants)
            if isinstance(effect, FrameEffect):
                effect.close_animators()

            # Clean up by removing from running registry
            async with self._lock:
                for member in members:
                    self._running.pop(participant_key(*member), None)

    async def _filter_compatible_lights(
        self, effect: LIFXEffect, participants: Sequence[Participant]
    ) -> list[Participant]:
        """Filter lights and light components based on effect requirements.

        Delegates compatibility checking to the effect's is_light_compatible()
        method, allowing effects to define their own requirements. A light
        component is checked through its light. It takes part only in effects
        that draw frames: suitability for its shape is advice, so an effect is
        refused only when it cannot draw on a light component at all.

        Args:
            effect: The effect to filter for
            participants: All lights and light components

        Returns:
            The participants compatible with the effect
        """

        # Check all participants in parallel using the effect's own check
        async def check_compatibility(
            participant: Participant,
        ) -> tuple[Participant, bool]:
            """Check if a single participant is compatible with the effect."""
            light, component = resolve(participant)
            if component is not None and not isinstance(effect, FrameEffect):
                is_compatible = False
            else:
                is_compatible = await effect.is_light_compatible(light)

            if not is_compatible:
                _LOGGER.debug(
                    {
                        "class": "Conductor",
                        "method": "_filter_compatible_lights",
                        "action": "filter",
                        "values": {
                            "serial": light.serial,
                            "component": component,
                            "effect": type(effect).__name__,
                            "compatible": False,
                        },
                    }
                )

            return (participant, is_compatible)

        results = await asyncio.gather(
            *(check_compatibility(participant) for participant in participants)
        )

        # Filter to only compatible participants
        return [participant for participant, is_compatible in results if is_compatible]

    async def _power_on_components(
        self, effect: LIFXEffect, participants: Sequence[Participant]
    ) -> None:
        """Turn on only the light components an effect starts on, where off.

        This happens before the light component draws, so its frames start on
        a light whose other light component is already dark. A light that is
        on is left as it is, and so is every whole-light participant: the
        effect powers those on itself.

        Args:
            effect: The effect about to start
            participants: The lights and light components it starts on
        """
        if not effect.power_on:
            return
        for participant in participants:
            if isinstance(participant, LightComponent):
                await power_on_component(
                    participant.light, participant.name, POWER_ON_TRANSITION_DURATION
                )

    async def _create_animators(
        self, effect: FrameEffect, participants: Sequence[Participant]
    ) -> list[AnimatorWriter]:
        """Borrow each participant's own Animator for this effect run.

        Every light owns one Animator (``light.animator``), shared with
        direct frame senders such as LedFx, so the effect's frames and theirs
        go through one writer and one ack gate. The effect draws through a
        writer with its own canvas and transition duration. A light
        component's writer draws on its slot of its light's Animator.

        Args:
            effect: The frame effect (used to determine duration_ms from fps)
            participants: Lights and light components to borrow Animators for

        Returns:
            List of writers, one per participant, and one per ring of a
            whole-light Mirror
        """
        # Use 1.5x frame interval for duration so transitions overlap.
        # This prevents micro-gaps from asyncio scheduling jitter.
        duration_ms = int(1500 / effect.fps)
        writers: list[AnimatorWriter] = []

        for participant in participants:
            if isinstance(participant, LightComponent):
                writers.append(
                    await component_writer(
                        participant.light, participant.name, duration_ms
                    )
                )
                continue
            rings = ring_names(participant)
            if rings:
                # A whole-light Mirror effect draws each ring through a writer
                light = cast("ComponentMatrixLight", participant)
                for ring in rings:
                    writers.append(
                        await component_writer(
                            light, ring, duration_ms, whole_light=True
                        )
                    )
                continue
            # start() and add_lights() already applied the Thread guard.
            animator = await participant.animator.prepare(enable_thread=True)
            writers.append(animator._writer(duration_ms=duration_ms))

        return writers

    def __repr__(self) -> str:
        """String representation of Conductor."""
        return f"Conductor(running_effects={len(self._running)})"


def _refuse_thread_frames(
    effect: LIFXEffect,
    participants: Sequence[Participant],
    caller: str,
    *,
    enable_thread: bool,
) -> None:
    """Refuse a frame-drawing effect if any participant's light is Thread.

    Checked before anything is captured or changed, so a refusal leaves
    every participant as it was. See ``Conductor.start()``.

    Raises:
        LifxUnsupportedCommandError: If the effect draws frames, a
            participant's light is evidenced as Thread and
            ``enable_thread`` is False
    """
    if not isinstance(effect, FrameEffect) or not effect._streams_frames:
        return
    for participant in participants:
        resolve(participant)[0]._refuse_thread_frames(
            caller, enable_thread=enable_thread
        )


class _LightEffects:
    """The effect runner lights use for their own start and stop calls.

    Each light keeps one Conductor for runs started on it, or on one of its
    light components, directly.
    """

    def __init__(self) -> None:
        self._conductors: weakref.WeakKeyDictionary[Light, Conductor] = (
            weakref.WeakKeyDictionary()
        )

    def conductor_for(self, light: Light) -> Conductor:
        """The Conductor a light keeps for runs started on it directly."""
        conductor = self._conductors.get(light)
        if conductor is None:
            conductor = Conductor()
            self._conductors[light] = conductor
        return conductor

    async def start(
        self,
        participant: Participant,
        effect: object,
        *,
        enable_thread: bool = False,
    ) -> None:
        """Start a software effect on one light or light component alone.

        Raises:
            TypeError: If ``effect`` is not a software effect, or a light
                component's effect does not draw frames
        """
        if isinstance(participant, LightComponent):
            if not isinstance(effect, FrameEffect):
                raise TypeError(
                    "A light component runs software effects that draw frames, "
                    f"not {type(effect).__name__}"
                )
        elif not isinstance(effect, LIFXEffect):
            raise TypeError(
                f"start_effect() takes a software effect, got {type(effect).__name__}"
            )
        # Refuse here so the message names the method the caller used.
        _refuse_thread_frames(
            effect, [participant], "start_effect()", enable_thread=enable_thread
        )
        await self.conductor_for(resolve(participant)[0]).start(
            effect, [participant], enable_thread=enable_thread
        )

    async def leave_every_run(
        self, participant: Participant, *, restore_state: bool = True
    ) -> None:
        """Remove a light or light component from every run it is part of."""
        await Conductor._leave_every_run(participant, restore_state=restore_state)

    def runs_whole_light(self, light: Light) -> bool:
        """Whether a whole-light software effect runs on a light."""
        return Conductor._runs_whole_light(light)


_LIGHT_EFFECTS = _LightEffects()
register_effect_runner(_LIGHT_EFFECTS)


def own_conductor(light: Light) -> Conductor:
    """The Conductor a light keeps for runs started on it, or its light components.

    ``light.start_effect()`` and a light component's ``start_effect()`` run
    their effect on this Conductor.
    """
    return _LIGHT_EFFECTS.conductor_for(light)
