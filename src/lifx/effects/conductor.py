"""Conductor orchestrator for managing light effects.

This module provides the Conductor class that coordinates effect lifecycle
across multiple devices.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from lifx.effects.models import PreState, RunningEffect
from lifx.effects.state_manager import DeviceStateManager

if TYPE_CHECKING:
    from lifx.devices.light import Light
    from lifx.effects.base import LIFXEffect

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
                captured: list[tuple[str, PreState]] = [None] * len(  # type: ignore
                    lights_needing_capture
                )

                async with asyncio.TaskGroup() as tg:
                    for capture_idx, (_, light) in enumerate(lights_needing_capture):

                        async def capture_and_store(cidx: int, device: Light) -> None:
                            prestate = await self._state_manager.capture_state(device)
                            captured[cidx] = (device.serial, prestate)
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

                        tg.create_task(capture_and_store(capture_idx, light))

                # Store captured prestates
                for serial, prestate in captured:
                    prestates[serial] = prestate

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
                async with asyncio.TaskGroup() as tg:
                    for light, prestate in lights_to_restore:
                        tg.create_task(
                            self._state_manager.restore_state(light, prestate)
                        )

            # Remove from running registry after restoration
            for light in lights:
                serial = light.serial
                if serial in self._running:
                    del self._running[serial]

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
                lights_to_restore: list[tuple[Light, PreState]] = []
                for light in participants:
                    serial = light.serial
                    running = self._running.get(serial)
                    if running:
                        lights_to_restore.append((light, running.prestate))

                # Restore all lights in parallel
                if lights_to_restore:
                    async with asyncio.TaskGroup() as tg:
                        for light, prestate in lights_to_restore:
                            tg.create_task(
                                self._state_manager.restore_state(light, prestate)
                            )

                # Remove from running registry after restoration
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
        results: list[tuple[Light, bool]] = []

        async def check_and_store(light: Light) -> None:
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

            results.append((light, is_compatible))

        async with asyncio.TaskGroup() as tg:
            for light in participants:
                tg.create_task(check_and_store(light))

        # Filter to only compatible lights
        compatible = [light for light, is_compatible in results if is_compatible]

        return compatible

    def __repr__(self) -> str:
        """String representation of Conductor."""
        return f"Conductor(running_effects={len(self._running)})"
