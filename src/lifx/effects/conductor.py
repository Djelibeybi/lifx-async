"""Conductor orchestrator for managing light effects.

This module provides the Conductor class that coordinates effect lifecycle
across multiple devices.
"""

from __future__ import annotations

import asyncio
import logging
import weakref
from typing import TYPE_CHECKING, ClassVar

from lifx.animation.animator import AnimatorWriter
from lifx.color import HSBK
from lifx.effects.models import (
    ParticipantKey,
    PreState,
    RunningEffect,
    participant_key,
)
from lifx.effects.state_manager import DeviceStateManager

if TYPE_CHECKING:
    from lifx.devices.light import Light
    from lifx.effects.base import LIFXEffect
    from lifx.effects.frame_effect import FrameEffect

_LOGGER = logging.getLogger(__name__)


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
        self, effect: LIFXEffect, lights: list[Light]
    ) -> dict[ParticipantKey, PreState]:
        """Stop the software effect each light already runs, on any Conductor.

        The light leaves its old run with no restore, so it never flashes back
        to its prior state; the old run's other participants carry on, and a
        run left with no participants is cancelled. Where ``effect`` inherits
        from the old effect (``inherit_prestate()``), the old run's prior
        state is returned for the light, so a later stop restores what was
        there before any effect.

        Args:
            effect: The effect about to start on the lights
            lights: The lights it is about to start on

        Returns:
            The inherited prior state of each light that has one
        """
        inherited: dict[ParticipantKey, PreState] = {}
        for light in lights:
            key = participant_key(light)
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
                                "serial": light.serial,
                                "previous_effect": type(running.effect).__name__,
                                "new_effect": type(effect).__name__,
                            },
                        }
                    )
                await conductor.remove_lights([light], restore_state=False)
        return inherited

    @classmethod
    async def _leave_every_run(cls, light: Light) -> None:
        """Remove a light from every run it is part of, on any Conductor.

        The light's prior state is restored and the other participants of
        each run carry on. Runs are matched by participant key, so a second
        object for the same light finds them too.

        Args:
            light: The light leaving its runs
        """
        key = participant_key(light)
        for conductor in list(cls._live):
            if key in conductor._running:
                await conductor.remove_lights([light])

    def effect(self, light: Light) -> LIFXEffect | None:
        """Return the effect currently running on a device, or None if idle.

        Args:
            light: The device to check

        Returns:
            Currently running LIFXEffect instance, or None

        Example:
            ```python
            current_effect = conductor.effect(light)
            if current_effect:
                print(f"Running: {type(current_effect).__name__}")
            ```
        """
        running = self._running.get(participant_key(light))
        return running.effect if running else None

    def get_last_frame(self, light: Light) -> list[HSBK] | None:
        """Return the most recent HSBK frame sent to a device, or None.

        For frame-based effects, returns the list of HSBK colors from the
        most recent call to generate_frame() for this device. Returns None
        if no effect is running on the device, the effect is not frame-based,
        no frame has been generated yet, or the effect overrides
        generate_protocol_frame() directly (bypassing HSBK construction).

        Args:
            light: The device to query

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
        running = self._running.get(participant_key(light))
        if not running:
            return None

        from lifx.effects.frame_effect import FrameEffect

        effect = running.effect
        if isinstance(effect, FrameEffect):
            return effect._last_frames.get(participant_key(light))
        return None

    async def start(
        self,
        effect: LIFXEffect,
        participants: list[Light],
    ) -> None:
        """Start an effect on one or more lights.

        Captures current light state, powers on if needed, and launches
        the effect. State is automatically restored when effect completes
        or stop() is called.

        Args:
            effect: The effect instance to execute
            participants: List of Light instances to apply effect to

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

            # Determine which lights need new prestate capture
            lights_needing_capture: list[tuple[int, Light]] = []
            prestates: dict[ParticipantKey, PreState] = {}

            for idx, light in enumerate(filtered_participants):
                key = participant_key(light)
                if key in inherited:
                    prestates[key] = inherited[key]
                else:
                    lights_needing_capture.append((idx, light))

            # Capture prestates in parallel for all lights that need it
            if lights_needing_capture:

                async def capture_and_log(
                    device: Light,
                ) -> tuple[ParticipantKey, PreState]:
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
                    return (participant_key(device), prestate)

                captured = await asyncio.gather(
                    *(capture_and_log(light) for _, light in lights_needing_capture)
                )

                # Store captured prestates
                for key, prestate in captured:
                    prestates[key] = prestate

            # Set up animators for frame-based effects
            from lifx.effects.frame_effect import FrameEffect

            if isinstance(effect, FrameEffect):
                # Set participants early so async_setup() can access them
                # (async_perform() sets this too but runs in a background task)
                effect.participants = filtered_participants
                animators = await self._create_animators(effect, filtered_participants)
                effect._animators = animators
                await effect.async_setup(filtered_participants)

            # Create background task for the effect
            task = asyncio.create_task(
                self._run_effect_with_cleanup(effect, filtered_participants)
            )

            # Register running effects for all participants
            for light in filtered_participants:
                key = participant_key(light)
                self._running[key] = RunningEffect(
                    effect=effect,
                    prestate=prestates[key],
                    task=task,
                )

    async def stop(self, lights: list[Light]) -> None:
        """Stop effects and restore light state.

        Halts any running effects on the specified lights and restores
        them to their pre-effect state (power, color, zones).

        Args:
            lights: List of lights to stop

        Example:
            ```python
            # Stop all lights
            await conductor.stop(group.lights)

            # Stop specific lights
            await conductor.stop([light1, light2])
            ```
        """
        async with self._lock:
            # Collect lights that need restoration and tasks to cancel
            lights_to_restore: list[tuple[Light, PreState]] = []
            tasks_to_cancel: set[asyncio.Task[None]] = set()

            for light in lights:
                running = self._running.get(participant_key(light))

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
                    lights_to_restore.append((light, running.prestate))
                    tasks_to_cancel.add(running.task)

            # Close animators for frame effects (once per effect, not per device)
            from lifx.effects.frame_effect import FrameEffect

            closed_effects: set[int] = set()
            for light in lights:
                running = self._running.get(participant_key(light))
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
            # Restore all lights in parallel
            if lights_to_restore:
                await asyncio.gather(
                    *(
                        self._state_manager.restore_state(light, prestate)
                        for light, prestate in lights_to_restore
                    )
                )

            # Remove from running registry after restoration
            for light in lights:
                self._running.pop(participant_key(light), None)

    async def add_lights(self, effect: LIFXEffect, lights: list[Light]) -> None:
        """Add lights to a running effect without restarting it.

        Captures state, creates animators (for FrameEffects), and registers
        lights as participants of the already-running effect. Lights that
        are already running this effect or are incompatible are skipped.

        Args:
            effect: The effect to add lights to (must already be running)
            lights: List of lights to add

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
            # Skip lights already running this effect
            new_lights: list[Light] = []
            for light in compatible:
                running = self._running.get(participant_key(light))
                if running and running.effect is effect:
                    continue
                new_lights.append(light)

            if not new_lights:
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
                            "lights": len(new_lights),
                        },
                    }
                )
                return

            # Capture prestates in parallel for lights that do not inherit one
            to_capture = [
                light for light in new_lights if participant_key(light) not in inherited
            ]
            captured = await asyncio.gather(
                *(self._state_manager.capture_state(light) for light in to_capture)
            )
            prestates = dict(inherited)
            prestates.update(
                zip([participant_key(light) for light in to_capture], captured)
            )

            # Create animators for frame-based effects
            from lifx.effects.frame_effect import FrameEffect

            if isinstance(effect, FrameEffect):
                new_animators = await self._create_animators(effect, new_lights)
                effect._animators.extend(new_animators)

            # Add to participants
            effect.participants.extend(new_lights)

            # Register in running map
            for light in new_lights:
                key = participant_key(light)
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
                        "added_count": len(new_lights),
                    },
                }
            )

    async def remove_lights(
        self, lights: list[Light], restore_state: bool = True
    ) -> None:
        """Remove lights from their running effect without stopping others.

        Closes animators, optionally restores state, and deregisters lights.
        If the last participant is removed, cancels the background task.

        Args:
            lights: List of lights to remove
            restore_state: Whether to restore pre-effect state (default True)

        Example:
            ```python
            # Remove a light and restore its state
            await conductor.remove_lights([light1])

            # Remove without restoring state
            await conductor.remove_lights([light2], restore_state=False)
            ```
        """
        from lifx.effects.frame_effect import FrameEffect

        tasks_to_cancel: set[asyncio.Task[None]] = set()
        lights_to_restore: list[tuple[Light, PreState]] = []

        async with self._lock:
            for light in lights:
                key = participant_key(light)
                running = self._running.get(key)
                if not running:
                    continue

                effect = running.effect

                # Remove animator for frame effects
                if isinstance(effect, FrameEffect):
                    # Find index by matching key in participants
                    for idx, participant in enumerate(effect.participants):
                        if participant_key(participant) == key:
                            if idx < len(effect._animators):
                                effect._animators[idx].close()
                                effect._animators.pop(idx)
                            break

                # Remove from participants
                effect.participants = [
                    p for p in effect.participants if participant_key(p) != key
                ]

                # Track for restoration
                if restore_state:
                    lights_to_restore.append((light, running.prestate))

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
        if lights_to_restore:
            await asyncio.gather(
                *(
                    self._state_manager.restore_state(light, prestate)
                    for light, prestate in lights_to_restore
                )
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

            # Close animators for frame effects
            from lifx.effects.frame_effect import FrameEffect

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
                    lights_to_restore: list[tuple[Light, PreState]] = []
                    for light in participants:
                        running = self._running.get(participant_key(light))
                        if running:
                            lights_to_restore.append((light, running.prestate))

                    # Restore all lights in parallel
                    if lights_to_restore:
                        await asyncio.gather(
                            *(
                                self._state_manager.restore_state(light, prestate)
                                for light, prestate in lights_to_restore
                            )
                        )

                # Remove from running registry
                for light in participants:
                    self._running.pop(participant_key(light), None)

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

            if isinstance(effect, FrameEffect):
                effect.close_animators()

            # Clean up by removing from running registry
            async with self._lock:
                for light in participants:
                    self._running.pop(participant_key(light), None)

    async def _filter_compatible_lights(
        self, effect: LIFXEffect, participants: list[Light]
    ) -> list[Light]:
        """Filter lights based on effect requirements.

        Delegates compatibility checking to the effect's is_light_compatible()
        method, allowing effects to define their own requirements.

        Args:
            effect: The effect to filter for
            participants: List of all lights

        Returns:
            List of lights compatible with the effect
        """

        # Check all lights in parallel using effect's compatibility check
        async def check_compatibility(light: Light) -> tuple[Light, bool]:
            """Check if a single light is compatible with the effect."""
            is_compatible = await effect.is_light_compatible(light)

            if not is_compatible:
                _LOGGER.debug(
                    {
                        "class": "Conductor",
                        "method": "_filter_compatible_lights",
                        "action": "filter",
                        "values": {
                            "serial": light.serial,
                            "effect": type(effect).__name__,
                            "compatible": False,
                        },
                    }
                )

            return (light, is_compatible)

        results = await asyncio.gather(
            *(check_compatibility(light) for light in participants)
        )

        # Filter to only compatible lights
        compatible = [light for light, is_compatible in results if is_compatible]

        return compatible

    async def _create_animators(
        self, effect: FrameEffect, participants: list[Light]
    ) -> list[AnimatorWriter]:
        """Borrow each participant's own Animator for this effect run.

        Every light owns one Animator (``light.animator``), shared with
        direct frame senders such as LedFx, so the effect's frames and theirs
        go through one writer and one ack gate. The effect draws through a
        writer with its own canvas and transition duration.

        Args:
            effect: The frame effect (used to determine duration_ms from fps)
            participants: List of lights to borrow Animators from

        Returns:
            List of writers, one per participant
        """
        from lifx.devices.mirror import MirrorLight

        # Use 1.5x frame interval for duration so transitions overlap.
        # This prevents micro-gaps from asyncio scheduling jitter.
        duration_ms = int(1500 / effect.fps)
        writers: list[AnimatorWriter] = []

        for light in participants:
            animator = await light.animator.prepare()
            if isinstance(light, MirrorLight):
                # A whole-light effect draws one ring frame on both rings.
                writer = animator._writer(
                    rings=[light.front_positions, light.back_positions],
                    duration_ms=duration_ms,
                )
            else:
                writer = animator._writer(duration_ms=duration_ms)
            writers.append(writer)

        return writers

    def __repr__(self) -> str:
        """String representation of Conductor."""
        return f"Conductor(running_effects={len(self._running)})"
