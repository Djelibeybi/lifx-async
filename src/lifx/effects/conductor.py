"""Conductor orchestrator for managing light effects.

This module provides the Conductor class that coordinates effect lifecycle
across multiple devices.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from lifx.color import HSBK
from lifx.effects.models import PreState, RunningEffect
from lifx.effects.state_manager import DeviceStateManager

if TYPE_CHECKING:
    from lifx.animation.animator import Animator
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
        _running: Dictionary mapping device serial to RunningEffect
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
        self._running: dict[str, RunningEffect] = {}
        self._lock = asyncio.Lock()

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
        running = self._running.get(light.serial)
        return running.effect if running else None

    def get_last_frame(self, light: Light) -> list[HSBK] | None:
        """Return the most recent HSBK frame sent to a device, or None.

        For frame-based effects, returns the list of HSBK colors from the
        most recent call to generate_frame() for this device. Returns None
        if no effect is running on the device, the effect is not frame-based,
        or no frame has been generated yet.

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
        running = self._running.get(light.serial)
        if not running:
            return None

        from lifx.effects.frame_effect import FrameEffect

        effect = running.effect
        if isinstance(effect, FrameEffect):
            return effect._last_frames.get(light.serial)
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

        async with self._lock:
            # Set conductor reference in effect
            effect.conductor = self

            # Determine which lights need new prestate capture
            lights_needing_capture: list[tuple[int, Light]] = []
            prestates: dict[str, PreState] = {}

            for idx, light in enumerate(filtered_participants):
                serial = light.serial
                current_running = self._running.get(serial)

                if current_running and effect.inherit_prestate(current_running.effect):
                    # Reuse existing prestate
                    prestates[serial] = current_running.prestate
                    effect_name = type(current_running.effect).__name__
                    _LOGGER.debug(
                        {
                            "class": self.__class__.__name__,
                            "method": "start",
                            "action": "inherit_prestate",
                            "values": {
                                "serial": serial,
                                "previous_effect": effect_name,
                                "new_effect": type(effect).__name__,
                            },
                        }
                    )
                else:
                    # Mark for capture
                    lights_needing_capture.append((idx, light))

            # Capture prestates in parallel for all lights that need it
            if lights_needing_capture:

                async def capture_and_log(device: Light) -> tuple[str, PreState]:
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
                    return (device.serial, prestate)

                captured = await asyncio.gather(
                    *(capture_and_log(light) for _, light in lights_needing_capture)
                )

                # Store captured prestates
                for serial, prestate in captured:
                    prestates[serial] = prestate

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
                serial = light.serial
                self._running[serial] = RunningEffect(
                    effect=effect,
                    prestate=prestates[serial],
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
                serial = light.serial
                running = self._running.get(serial)

                if running:
                    _LOGGER.debug(
                        {
                            "class": self.__class__.__name__,
                            "method": "stop",
                            "action": "stop",
                            "values": {
                                "serial": serial,
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
                running = self._running.get(light.serial)
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
                serial = light.serial
                if serial in self._running:
                    del self._running[serial]

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

        async with self._lock:
            # Skip lights already running this effect
            new_lights: list[Light] = []
            for light in compatible:
                running = self._running.get(light.serial)
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

            # Capture prestates in parallel
            captured = await asyncio.gather(
                *(self._state_manager.capture_state(light) for light in new_lights)
            )
            prestates = dict(zip([light.serial for light in new_lights], captured))

            # Create animators for frame-based effects
            from lifx.effects.frame_effect import FrameEffect

            if isinstance(effect, FrameEffect):
                new_animators = await self._create_animators(effect, new_lights)
                effect._animators.extend(new_animators)

            # Add to participants
            effect.participants.extend(new_lights)

            # Register in running map
            for light in new_lights:
                self._running[light.serial] = RunningEffect(
                    effect=effect,
                    prestate=prestates[light.serial],
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
                serial = light.serial
                running = self._running.get(serial)
                if not running:
                    continue

                effect = running.effect

                # Remove animator for frame effects
                if isinstance(effect, FrameEffect):
                    # Find index by matching serial in participants
                    for idx, participant in enumerate(effect.participants):
                        if participant.serial == serial:
                            if idx < len(effect._animators):
                                effect._animators[idx].close()
                                effect._animators.pop(idx)
                            break

                # Remove from participants
                effect.participants = [
                    p for p in effect.participants if p.serial != serial
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

                del self._running[serial]

                _LOGGER.debug(
                    {
                        "class": self.__class__.__name__,
                        "method": "remove_lights",
                        "action": "removed",
                        "values": {
                            "serial": serial,
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
                        serial = light.serial
                        running = self._running.get(serial)
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
                    serial = light.serial
                    if serial in self._running:
                        del self._running[serial]

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
                    serial = light.serial
                    if serial in self._running:
                        del self._running[serial]

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
    ) -> list[Animator]:
        """Create animators for each participant based on device type.

        Args:
            effect: The frame effect (used to determine duration_ms from fps)
            participants: List of lights to create animators for

        Returns:
            List of Animator instances, one per participant
        """
        from lifx.animation.animator import Animator
        from lifx.devices.matrix import MatrixLight
        from lifx.devices.multizone import MultiZoneLight

        # Use 1.5x frame interval for duration so transitions overlap.
        # This prevents micro-gaps from asyncio scheduling jitter.
        duration_ms = int(1500 / effect.fps)
        animators: list[Animator] = []

        for light in participants:
            if isinstance(light, MatrixLight):
                animator = await Animator.for_matrix(light, duration_ms=duration_ms)
            elif isinstance(light, MultiZoneLight):
                animator = await Animator.for_multizone(light, duration_ms=duration_ms)
            else:
                animator = Animator.for_light(light, duration_ms=duration_ms)
            animators.append(animator)

        return animators

    def __repr__(self) -> str:
        """String representation of Conductor."""
        return f"Conductor(running_effects={len(self._running)})"
