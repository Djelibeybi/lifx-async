"""Frame-based effect base class for animation-driven effects.

This module provides FrameEffect, an abstract base class for effects that
generate color frames at a fixed FPS. Frame generation is separated from
delivery: effects implement generate_frame() returning user-friendly HSBK
colors, and the base class handles conversion and dispatch via the
animation module.
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from lifx.color import HSBK
from lifx.effects.base import LIFXEffect

if TYPE_CHECKING:
    from lifx.animation.animator import Animator
    from lifx.devices.light import Light

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class FrameContext:
    """Context passed to generate_frame() with timing and layout info.

    Attributes:
        elapsed_s: Seconds since effect started
        device_index: Index of this device in the participants list
        pixel_count: Number of pixels (1 for light, N for zones, W*H for matrix)
        canvas_width: Width in pixels (pixel_count for 1D, W for matrix)
        canvas_height: Height in pixels (1 for 1D, H for matrix)
    """

    elapsed_s: float
    device_index: int
    pixel_count: int
    canvas_width: int
    canvas_height: int


class FrameEffect(LIFXEffect):
    """Abstract base class for frame-generator effects.

    Subclass this to create effects that generate color frames at a fixed
    FPS. Implement generate_frame() to return a list of HSBK colors
    matching ctx.pixel_count.

    The Conductor creates Animators for each participant and sets them
    on this effect before starting. The frame loop handles timing,
    HSBK-to-protocol conversion, and frame dispatch.

    Attributes:
        fps: Frames per second
        duration: Effect duration in seconds, or None for infinite

    Example:
        ```python
        class RainbowEffect(FrameEffect):
            def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
                colors = []
                for i in range(ctx.pixel_count):
                    hue = (ctx.elapsed_s * 60 + i * 10) % 360
                    colors.append(
                        HSBK(hue=hue, saturation=1.0, brightness=0.8, kelvin=3500)
                    )
                return colors
        ```
    """

    def __init__(
        self,
        power_on: bool = True,
        fps: float = 30.0,
        duration: float | None = None,
    ) -> None:
        """Initialize frame effect.

        Args:
            power_on: Power on devices during effect (default True)
            fps: Frames per second (default 30.0, must be > 0)
            duration: Effect duration in seconds, or None for infinite

        Raises:
            ValueError: If fps <= 0 or duration <= 0
        """
        super().__init__(power_on=power_on)

        if fps <= 0:
            raise ValueError(f"fps must be positive, got {fps}")
        if duration is not None and duration <= 0:
            raise ValueError(f"duration must be positive, got {duration}")

        self._fps = fps
        self._duration = duration
        self._stop_event = asyncio.Event()
        self._animators: list[Animator] = []

    @property
    def fps(self) -> float:
        """Get frames per second."""
        return self._fps

    @property
    def duration(self) -> float | None:
        """Get effect duration in seconds, or None for infinite."""
        return self._duration

    @abstractmethod
    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        """Generate a frame of colors for one device.

        Called once per device per frame. Return a list of HSBK colors
        matching ctx.pixel_count.

        Args:
            ctx: Frame context with timing and layout info

        Returns:
            List of HSBK colors (length must equal ctx.pixel_count)
        """

    async def async_setup(self, _participants: list[Light]) -> None:
        """Optional setup hook called before the frame loop starts.

        Override this to perform async setup like fetching initial colors
        from devices. Called after animators are created but before
        the first frame.

        Args:
            participants: List of lights participating in the effect
        """

    async def async_play(self) -> None:
        """Run the frame loop.

        Iterates animators, creates FrameContext per device, calls
        generate_frame(), converts to protocol format, and sends frames.
        Runs until duration expires, stop() is called, or cancelled.
        """
        self._stop_event.clear()
        frame_interval = 1.0 / self._fps
        start_time = time.monotonic()

        while not self._stop_event.is_set():
            frame_start = time.monotonic()
            elapsed_s = frame_start - start_time

            # Check duration
            if self._duration is not None and elapsed_s >= self._duration:
                break

            # Generate and send frames for each device
            for idx, animator in enumerate(self._animators):
                ctx = FrameContext(
                    elapsed_s=elapsed_s,
                    device_index=idx,
                    pixel_count=animator.pixel_count,
                    canvas_width=animator.canvas_width,
                    canvas_height=animator.canvas_height,
                )

                # Generate user-friendly HSBK frame
                hsbk_frame = self.generate_frame(ctx)

                # Convert to protocol tuples
                protocol_frame = [color.as_tuple() for color in hsbk_frame]

                # Send via direct UDP
                animator.send_frame(protocol_frame)

            # Sleep for remaining frame time
            frame_elapsed = time.monotonic() - frame_start
            sleep_time = max(0.0, frame_interval - frame_elapsed)
            if sleep_time > 0:
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=sleep_time)
                    break  # Stop event was set
                except asyncio.TimeoutError:
                    pass  # Normal - continue to next frame

    def stop(self) -> None:
        """Signal the frame loop to stop."""
        self._stop_event.set()

    def close_animators(self) -> None:
        """Close all animators and clear the list.

        Called by the Conductor during cleanup.
        """
        for animator in self._animators:
            animator.close()
        self._animators.clear()
