"""Conductor orchestrator for managing light effects.

This module provides the Conductor class that coordinates effect lifecycle
across multiple devices.
"""

from __future__ import annotations

import asyncio
import logging
import weakref
from collections.abc import Sequence
from typing import TYPE_CHECKING, ClassVar, cast

from lifx.animation.animator import AnimatorWriter
from lifx.color import HSBK
from lifx.devices.component.participant import LightComponent
from lifx.effects.const import POWER_ON_TRANSITION_DURATION
from lifx.effects.models import (
    ParticipantKey,
    PreState,
    RunningEffect,
    participant_key,
)
from lifx.effects.state_manager import DeviceStateManager

if TYPE_CHECKING:
    from lifx.devices.component.light import ComponentMatrixLight
    from lifx.devices.light import Light
    from lifx.effects.base import LIFXEffect
    from lifx.effects.frame_effect import FrameEffect

    # An effect participant: a whole light, or one light component of a light.
    Participant = Light | LightComponent

_LOGGER = logging.getLogger(__name__)


def _resolve(participant: Participant) -> tuple[Light, str | None]:
    """Split an effect participant into its light and light component."""
    if isinstance(participant, LightComponent):
        return participant._light, participant._name
    return participant, None


def _key(participant: Participant) -> ParticipantKey:
    """Return the Conductor key for an effect participant."""
    return participant_key(*_resolve(participant))


def _members(effect: LIFXEffect, lights: list[Light]) -> list[tuple[Light, str | None]]:
    """Pair each light of an effect with the light component it takes part as.

    A frame effect's borrowed writers line up with its participants, and a
    light component's writer names its light component. A writer drawing a
    ring of a whole-light Mirror effect belongs to the whole light.
    """
    from lifx.effects.frame_effect import FrameEffect, writer_participant

    writers = effect._animators if isinstance(effect, FrameEffect) else []
    return [
        (light, writer_participant(writers[idx]) if idx < len(writers) else None)
        for idx, light in enumerate(lights)
    ]


def _rings(participant: Participant) -> tuple[str, ...]:
    """The rings a whole-light effect draws on, one effect participant each.

    A whole-light effect on a Mirror runs as two ring participants, its front
    and back, so each ring is a canvas that wraps. Any other participant
    draws as itself.
    """
    from lifx.devices.mirror import MirrorLight

    if isinstance(participant, MirrorLight):
        return ("front", "back")
    return ()


def _drawn_lights(
    effect: LIFXEffect, participants: Sequence[Participant]
) -> list[Light]:
    """The light of each participant, in writer order for a frame effect.

    A frame effect draws a whole-light Mirror once for each ring; any other
    effect takes part on the light once.
    """
    from lifx.effects.frame_effect import FrameEffect

    drawn = isinstance(effect, FrameEffect)
    return [
        light
        for participant in participants
        for light in [_resolve(participant)[0]]
        * (max(len(_rings(participant)), 1) if drawn else 1)
    ]


class Conductor:
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

    # Every live Conductor, so device.stop_effect() can find a run the light
    # is part of without the device holding a link to each Conductor.
    _live: ClassVar[weakref.WeakSet[Conductor]] = weakref.WeakSet()

    def __init__(self) -> None:
        """Initialize the Conductor."""
        self._state_manager = DeviceStateManager()
        self._running: dict[ParticipantKey, RunningEffect] = {}
        self._lock = asyncio.Lock()
        Conductor._live.add(self)

    async def _take_over(
        self, effect: LIFXEffect, participants: Sequence[Participant]
    ) -> dict[ParticipantKey, PreState]:
        """Stop the software effect each light already runs, on any Conductor.

        The light leaves its old run with no restore, so it never flashes back
        to its prior state; the old run's other participants carry on, and a
        run left with no participants is cancelled. Where ``effect`` inherits
        from the old effect (``inherit_prestate()``), the old run's prior
        state is returned for the light, so a later stop restores what was
        there before any effect.

        Args:
            effect: The effect about to start on the participants
            participants: The lights and light components it is about to
                start on

        Returns:
            The inherited prior state of each participant that has one
        """
        inherited: dict[ParticipantKey, PreState] = {}
        for participant in participants:
            key = _key(participant)
            for conductor in list(Conductor._live):
                running = conductor._running.get(key)
                if running is None or running.effect is effect:
                    continue
                if effect.inherit_prestate(running.effect):
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
        return inherited

    @classmethod
    async def _leave_every_run(
        cls, participant: Participant, *, restore_state: bool = True
    ) -> None:
        """Remove a participant from every run it is part of, on any Conductor.

        The participant's prior state is restored, unless ``restore_state`` is
        False, and the other participants of each run carry on. A whole light
        also leaves the runs of its light components. Runs are matched by
        participant key, so a second object for the same light finds them too.

        Args:
            participant: The light or light component leaving its runs
            restore_state: Whether to restore the participant's prior state
        """
        light, component = _resolve(participant)
        for conductor in list(cls._live):
            members = [
                (light, key[1] if isinstance(key, tuple) else None)
                for key in conductor._running
                if key == _key(participant)
                or (
                    component is None
                    and isinstance(key, tuple)
                    and key[0] == light.serial
                )
            ]
            if members:
                await conductor._remove(members, restore_state=restore_state)

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
        running = self._running.get(_key(light))
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
        key = _key(light)
        running = self._running.get(key)
        if not running:
            return None

        from lifx.effects.frame_effect import FrameEffect

        effect = running.effect
        if not isinstance(effect, FrameEffect):
            return None
        frame = effect._last_frames.get(key)
        rings = _rings(light)
        if frame is None and rings:
            # A whole-light Mirror effect draws each ring as a participant:
            # its frame is every ring's frame in turn, so zone order.
            frames = [
                effect._last_frames.get(participant_key(cast("Light", light), ring))
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
    ) -> None:
        """Start an effect on one or more lights or light components.

        Captures current light state, powers on if needed, and launches
        the effect. State is automatically restored when effect completes
        or stop() is called.

        A light component, such as ``ceiling.downlight``, takes part only in
        effects that draw frames; any other effect leaves it out.

        Args:
            effect: The effect instance to execute
            participants: Lights and light components to apply effect to

        Raises:
            LifxTimeoutError: If light state capture times out
            LifxDeviceNotFoundError: If light becomes unreachable

        Example:
            ```python
            # Start pulse effect on all lights
            effect = EffectPulse(mode="breathe", cycles=3)
            await conductor.start(effect, group.lights)
            ```
        """
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
        inherited = await self._take_over(effect, filtered_participants)

        async with self._lock:
            # Set conductor reference in effect
            effect.conductor = self
            members = [_resolve(p) for p in filtered_participants]
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

            # Set up animators for frame-based effects
            from lifx.effects.frame_effect import FrameEffect

            if isinstance(effect, FrameEffect):
                # Set participants early so async_setup() can access them
                # (async_perform() sets this too but runs in a background task).
                # A whole-light Mirror takes part once for each ring.
                lights = _drawn_lights(effect, filtered_participants)
                effect.participants = lights
                await self._power_on_components(effect, filtered_participants)
                animators = await self._create_animators(effect, filtered_participants)
                effect._animators = animators
                await effect.async_setup(lights)

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
        color, zones).

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
        async with self._lock:
            # Collect participants that need restoration and tasks to cancel
            to_restore: list[tuple[Light, str | None, PreState]] = []
            tasks_to_cancel: set[asyncio.Task[None]] = set()

            for participant in lights:
                light, component = _resolve(participant)
                running = self._running.get(participant_key(light, component))

                if running:
                    _LOGGER.debug(
                        {
                            "class": self.__class__.__name__,
                            "method": "stop",
                            "action": "stop",
                            "values": {
                                "serial": light.serial,
                                "effect": type(running.effect).__name__,
                            },
                        }
                    )
                    to_restore.append((light, component, running.prestate))
                    tasks_to_cancel.add(running.task)

            # Close animators for frame effects (once per effect, not per device)
            from lifx.effects.frame_effect import FrameEffect

            closed_effects: set[int] = set()
            for participant in lights:
                running = self._running.get(_key(participant))
                if running and isinstance(running.effect, FrameEffect):
                    effect_id = id(running.effect)
                    if effect_id not in closed_effects:
                        running.effect.close_animators()
                        closed_effects.add(effect_id)

            # Cancel background tasks
            for task in tasks_to_cancel:
                if not task.done():
                    task.cancel()

        # Wait for tasks to be cancelled (outside lock)
        if tasks_to_cancel:
            await asyncio.gather(*tasks_to_cancel, return_exceptions=True)

        async with self._lock:
            # Restore all participants in parallel
            if to_restore:
                await asyncio.gather(*(self._restore(*item) for item in to_restore))

            # Remove from running registry after restoration
            for participant in lights:
                self._running.pop(_key(participant), None)

    async def add_lights(
        self, effect: LIFXEffect, lights: Sequence[Participant]
    ) -> None:
        """Add lights or light components to a running effect without restarting it.

        Captures state, creates animators (for FrameEffects), and registers
        them as participants of the already-running effect. Participants
        that are already running this effect or are incompatible are skipped.

        Args:
            effect: The effect to add participants to (must already be running)
            lights: Lights and light components to add

        Example:
            ```python
            # Add a new light to an already-running effect
            await conductor.add_lights(effect, [new_light])
            ```
        """
        # Filter compatible lights
        compatible = await self._filter_compatible_lights(effect, lights)
        if not compatible:
            return

        # Newest wins, as in start(): a light running another effect leaves
        # that run with no restore in between. An effect that is not running
        # here takes no light from anywhere.
        inherited: dict[ParticipantKey, PreState] = {}
        if any(running.effect is effect for running in self._running.values()):
            inherited = await self._take_over(effect, compatible)

        async with self._lock:
            # Skip participants already running this effect
            new_participants: list[Participant] = []
            for participant in compatible:
                running = self._running.get(_key(participant))
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
            to_capture = [p for p in new_participants if _key(p) not in inherited]
            captured = await asyncio.gather(
                *(self._state_manager.capture_state(_resolve(p)[0]) for p in to_capture)
            )
            prestates = dict(inherited)
            prestates.update(zip([_key(p) for p in to_capture], captured))

            # Create animators for frame-based effects
            from lifx.effects.frame_effect import FrameEffect

            if isinstance(effect, FrameEffect):
                await self._power_on_components(effect, new_participants)
                new_animators = await self._create_animators(effect, new_participants)
                effect._animators.extend(new_animators)

            # Add to participants, a whole-light Mirror once for each ring
            effect.participants.extend(_drawn_lights(effect, new_participants))

            # Register in running map
            for participant in new_participants:
                key = _key(participant)
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
        lights or light components. If the last participant is removed,
        cancels the background task.

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
        await self._remove([_resolve(p) for p in lights], restore_state=restore_state)

    async def _remove(
        self, members: list[tuple[Light, str | None]], *, restore_state: bool
    ) -> None:
        """Remove each light or light component from its run; see remove_lights()."""
        from lifx.effects.frame_effect import FrameEffect

        tasks_to_cancel: set[asyncio.Task[None]] = set()
        to_restore: list[tuple[Light, str | None, PreState]] = []

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
                    for idx, member in enumerate(_members(effect, effect.participants))
                    if participant_key(*member) == key
                ]
                for idx in reversed(matched):
                    if isinstance(effect, FrameEffect) and idx < len(effect._animators):
                        effect._animators.pop(idx).close()
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
        self, light: Light, component: str | None, prestate: PreState
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
            from lifx.effects.frame_effect import FrameEffect

            members = _members(effect, participants)
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
                        ParticipantKey, tuple[Light, str | None, PreState]
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
            from lifx.effects.frame_effect import FrameEffect

            members = _members(effect, participants)
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
        from lifx.effects.frame_effect import FrameEffect

        # Check all participants in parallel using the effect's own check
        async def check_compatibility(
            participant: Participant,
        ) -> tuple[Participant, bool]:
            """Check if a single participant is compatible with the effect."""
            light, component = _resolve(participant)
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
                await participant._light._power_on_component(
                    participant._name, POWER_ON_TRANSITION_DURATION
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
                writers.append(await participant._writer(duration_ms))
                continue
            rings = _rings(participant)
            if rings:
                # A whole-light Mirror effect draws each ring as a participant
                light = cast("ComponentMatrixLight", participant)
                for ring in rings:
                    writers.append(
                        await light._component_writer(
                            ring, duration_ms, whole_light=True
                        )
                    )
                continue
            animator = await participant.animator.prepare()
            writers.append(animator._writer(duration_ms=duration_ms))

        return writers

    def __repr__(self) -> str:
        """String representation of Conductor."""
        return f"Conductor(running_effects={len(self._running)})"
