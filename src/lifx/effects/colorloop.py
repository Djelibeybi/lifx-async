"""ColorLoop effect implementation.

This module provides the EffectColorloop class for continuous hue rotation.
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
import random
from typing import TYPE_CHECKING, Any

from lifx.animation.animator import AnimatorWriter
from lifx.color import HSBK
from lifx.const import KELVIN_NEUTRAL
from lifx.devices.base import Connectivity
from lifx.effects.base import LIFXEffect
from lifx.effects.frame_effect import FrameContext, FrameEffect

if TYPE_CHECKING:
    from lifx.devices.light import Light

_LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass
class _Schedule:
    """When a light, or a tile, is next written.

    Attributes:
        next_at: Elapsed seconds at which the last write's transition ends
            and the next write is due
        hold_version: The tile's held colours when it was last written
        streamed: True while the tile is streamed frame by frame, so the next
            step must be written as soon as the stream ends
    """

    next_at: float = 0.0
    hold_version: int = -1
    streamed: bool = True


def _on_thread(light: Light) -> bool:
    """Whether a light is evidenced as Thread, so it must not be streamed to."""
    return light._evidenced_connectivity() is Connectivity.THREAD


class EffectColorloop(FrameEffect):
    """Continuous color rotation effect cycling through hue spectrum.

    Perpetually cycles through hues with configurable speed, spread,
    and color constraints. Continues until stopped.

    The hue moves ``change`` degrees per step, and a full turn takes
    ``period`` seconds, so each step lasts ``period * change / 360`` seconds.
    Each light gets one colour write per step, with the step as its
    transition, and the firmware fades between them. It streams no frames,
    so it runs on Thread lights without ``enable_thread``.

    A light component of a Ceiling or Mirror shares one tile with the other
    light component, and is written the same way while colour loop has the
    tile to itself. While another effect draws on the other light component,
    that effect's frames carry colour loop's colour and colour loop sends
    nothing. While a fade the caller asked of the other light component runs,
    colour loop draws frames so the fade shows. On a Thread light it goes on
    writing once per step instead, and each write carries the other light
    component as far through its fade as it will be when the step ends, so
    the firmware follows that fade a step at a time; no write turns colour
    loop's hue further than ``change``.

    Attributes:
        period: Seconds per full cycle (default 60)
        change: Hue degrees to shift per step (default 20)
        spread: Hue degrees spread across devices (default 30)
        brightness: Fixed brightness, or None to preserve (default None)
        saturation_min: Minimum saturation (0.0-1.0, default 0.8)
        saturation_max: Maximum saturation (0.0-1.0, default 1.0)
        transition: Transition time of each step's write in seconds, or None
            for the step's length
        synchronized: If True, all lights show same color simultaneously (default False)

    Example:
        ```python
        # Rainbow effect with spread
        effect = EffectColorloop(period=30, change=30, spread=60)
        await conductor.start(effect, lights)

        # Synchronized colorloop - all lights same color
        effect = EffectColorloop(period=30, change=30, synchronized=True)
        await conductor.start(effect, lights)

        # Wait then stop
        await asyncio.sleep(120)
        await conductor.stop(lights)

        # Colorloop with fixed brightness
        effect = EffectColorloop(
            period=20, change=15, brightness=0.7, saturation_min=0.9
        )
        await conductor.start(effect, lights)
        ```
    """

    _streams_frames = False

    def __init__(
        self,
        power_on: bool = True,
        period: float = 60,
        change: float = 20,
        spread: float = 30,
        brightness: float | None = None,
        saturation_min: float = 0.8,
        saturation_max: float = 1.0,
        transition: float | None = None,
        synchronized: bool = False,
    ) -> None:
        """Initialize colorloop effect.

        Args:
            power_on: Power on devices if off (default True)
            period: Seconds per full cycle (default 60)
            change: Hue degrees to shift per step, more than 0 and less
                    than 180 (default 20). The firmware fades hue the short
                    way round, so a step of 180 or more would turn backwards.
            spread: Hue degrees spread across devices (default 30).
                    Ignored if synchronized=True.
            brightness: Fixed brightness, or None to preserve (default None)
            saturation_min: Minimum saturation (0.0-1.0, default 0.8)
            saturation_max: Maximum saturation (0.0-1.0, default 1.0)
            transition: Transition time of each step's write in seconds,
                        or None for the step's length (default None)
            synchronized: If True, all lights display the same color
                         simultaneously with consistent transitions. When False,
                         lights are spread across the hue spectrum based on
                         'spread' parameter (default False).

        Raises:
            ValueError: If parameters are out of valid ranges
        """
        if period <= 0:
            raise ValueError(f"Period must be positive, got {period}")
        if not (0 < change < 180):
            raise ValueError(
                f"Change must be more than 0 and less than 180 degrees, got {change}"
            )
        if not (0 <= spread <= 360):
            raise ValueError(f"Spread must be 0-360 degrees, got {spread}")
        if brightness is not None and not (0.0 <= brightness <= 1.0):
            raise ValueError(f"Brightness must be 0.0-1.0, got {brightness}")
        if not (0.0 <= saturation_min <= 1.0):
            raise ValueError(f"Saturation_min must be 0.0-1.0, got {saturation_min}")
        if not (0.0 <= saturation_max <= 1.0):
            raise ValueError(f"Saturation_max must be 0.0-1.0, got {saturation_max}")
        if saturation_min > saturation_max:
            raise ValueError(
                f"Saturation_min ({saturation_min}) must be <= "
                f"saturation_max ({saturation_max})"
            )
        if transition is not None and transition < 0:
            raise ValueError(f"Transition must be non-negative, got {transition}")

        # A light gets one write per step, but the loop still runs at 20 FPS
        # at least: it notices each step on time, and a light component that
        # shares its tile with another effect is drawn frame by frame.
        step = period * change / 360.0
        fps = max(20.0, 1.0 / step)

        super().__init__(power_on=power_on, fps=fps, duration=None)

        self.period = period
        self.change = change
        self.spread = spread
        self.brightness = brightness
        self.saturation_min = saturation_min
        self.saturation_max = saturation_max
        self.transition = transition
        self.synchronized = synchronized
        self._step = step

        # Runtime state (set during async_setup)
        self._initial_colors: list[HSBK] = []
        self._direction: int = 1
        self._schedules: dict[object, _Schedule] = {}
        self._writes: dict[object, asyncio.Task[None]] = {}

    @property
    def name(self) -> str:
        """Return the name of the effect.

        Returns:
            The effect name 'colorloop'
        """
        return "colorloop"

    async def async_setup(self, participants: list[Light]) -> None:
        """Fetch initial colors and pick rotation direction.

        Args:
            participants: List of lights participating in the effect
        """
        self._initial_colors = await self._get_initial_colors(participants)
        self._direction = random.choice([1, -1])

    async def async_play(self) -> None:
        """Run the loop, then cancel any colour write still in flight.

        A write that lands after the loop stops would overwrite the colours
        the Conductor restores.
        """
        self._schedules = {}
        try:
            await super().async_play()
        finally:
            writes = list(self._writes.values())
            self._writes.clear()
            for write in writes:
                write.cancel()
            await asyncio.gather(*writes, return_exceptions=True)

    def _deliver(
        self,
        idx: int,
        writer: Any,
        frame: list[tuple[int, int, int, int]],
        ctx: FrameContext,
        staged: bool,
    ) -> None:
        """Write the next step's colour once per step.

        Each light is written at the start of every step with the colour the
        step ends on, so the firmware does the fading. A light component's
        writer keeps its slot showing the colour of the moment, so another
        effect that starts on the tile picks up from there.

        Args:
            idx: The writer's index among the borrowed writers
            writer: The borrowed writer
            frame: This frame, drawn for the current moment
            ctx: The frame context the frame was drawn with
            staged: True if a later writer sends this writer's tile
        """
        slot = isinstance(writer, AnimatorWriter) and writer.draws_slot
        # Writers sharing a tile share one schedule: the last one sends it.
        key: object = writer.animator if slot else writer
        schedule = self._schedules.setdefault(key, _Schedule())
        if slot:
            if writer.tile_shared(self._animators):
                # Another effect's frames carry the slot.
                writer.streaming = False
                schedule.streamed = True
                writer.stage(frame)
                return
            if writer.hold_remaining > 0 and not _on_thread(self.participants[idx]):
                # Frames show the other light component's fade exactly.
                writer.streaming = True
                schedule.streamed = True
                super()._deliver(idx, writer, frame, ctx, staged)
                return
            writer.streaming = False

        now = ctx.elapsed_s
        version = writer.hold_version if slot else 0
        if (
            not schedule.streamed
            and now < schedule.next_at
            and version == schedule.hold_version
        ):
            if slot:
                writer.stage(frame)
            return

        step_ends_at = (int(now // self._step) + 1) * self._step
        ends_at = step_ends_at
        if slot:
            # One transition per tile: end no later than another slot's fade,
            # then write again, so neither fade is stretched.
            deadline = writer.slot_deadline(self._animators)
            if deadline is not None and 1 / self.fps <= deadline < ends_at - now:
                ends_at = now + deadline
        duration = ends_at - now
        if self.transition is not None:
            # A shortened write never runs past the fade it was shortened for.
            duration = (
                self.transition
                if ends_at == step_ends_at
                else min(self.transition, duration)
            )
        target = self.generate_frame(dataclasses.replace(ctx, elapsed_s=ends_at))
        if slot:
            # The slot's fade starts from the colour of the moment.
            writer.stage(frame)
            target_frame = [color.as_tuple() for color in target]
            duration_ms = round(duration * 1000)
            if staged:
                writer.stage(target_frame, settled=True, duration_ms=duration_ms)
                return
            stats = writer.send_frame(
                target_frame, duration_ms=duration_ms, settled=True
            )
            if stats.gated:
                return  # Still due: the next frame tries again
        else:
            self._write_color(writer, self.participants[idx], target[0], duration)
        schedule.next_at = ends_at
        schedule.hold_version = version
        schedule.streamed = False

    def _writer_closed(self, writer: object) -> None:
        """Cancel the colour write of a writer that left the run.

        Its light is about to be restored or handed to another effect, which
        a late write would overwrite.
        """
        write = self._writes.pop(writer, None)
        if write is not None:
            write.cancel()

    def _write_color(
        self, key: object, light: Light, color: HSBK, duration: float
    ) -> None:
        """Start a light's colour write, replacing one still in flight.

        Args:
            key: The writer the light is drawn through
            light: The light to write
            color: The colour the step ends on
            duration: Transition time in seconds
        """
        previous = self._writes.pop(key, None)
        if previous is not None:
            previous.cancel()
        self._writes[key] = asyncio.create_task(self._set_color(light, color, duration))

    async def _set_color(self, light: Light, color: HSBK, duration: float) -> None:
        """Write one step's colour, logging a failure; the next step retries."""
        try:
            await light.set_color(color, duration=duration)
        except Exception as error:
            _LOGGER.warning(
                {
                    "class": self.__class__.__name__,
                    "method": "_set_color",
                    "action": "change",
                    "error": str(error),
                    "values": {"serial": light.serial, "duration": duration},
                }
            )

    def generate_frame(self, ctx: FrameContext) -> list[HSBK]:
        """Generate a frame of colors for one device.

        All pixels on a device receive the same color. For multizone/matrix
        devices that need per-pixel rainbow effects, use EffectRainbow instead.

        Args:
            ctx: Frame context with timing and layout info

        Returns:
            List of HSBK colors (length equals ctx.pixel_count)
        """
        if not self._initial_colors:
            # Fallback if setup hasn't run yet
            return [
                HSBK(hue=0, saturation=1.0, brightness=0.8, kelvin=3500)
            ] * ctx.pixel_count

        # Calculate hue rotation from elapsed time
        # degrees_rotated = (elapsed / period) * 360 * direction
        degrees_rotated = (ctx.elapsed_s / self.period) * 360.0 * self._direction

        if self.synchronized:
            color = self._generate_synchronized_color(degrees_rotated)
        else:
            color = self._generate_spread_color(degrees_rotated, ctx.device_index)

        return [color] * ctx.pixel_count

    def _generate_synchronized_color(self, degrees_rotated: float) -> HSBK:
        """Generate color for synchronized mode.

        All devices get the same color based on the first light's initial hue.

        Args:
            degrees_rotated: Total degrees of hue rotation

        Returns:
            HSBK color for this frame
        """
        base_hue = self._initial_colors[0].hue if self._initial_colors else 0
        new_hue = round((base_hue + degrees_rotated) % 360)

        # Consistent saturation for synchronization
        shared_saturation = (self.saturation_min + self.saturation_max) / 2

        # Calculate shared brightness
        if self.brightness is not None:
            shared_brightness = self.brightness
        else:
            shared_brightness = sum(c.brightness for c in self._initial_colors) / len(
                self._initial_colors
            )

        # Calculate shared kelvin
        shared_kelvin = int(
            sum(c.kelvin for c in self._initial_colors) / len(self._initial_colors)
        )

        return HSBK(
            hue=new_hue,
            saturation=shared_saturation,
            brightness=shared_brightness,
            kelvin=shared_kelvin,
        )

    def _generate_spread_color(self, degrees_rotated: float, device_index: int) -> HSBK:
        """Generate color for spread mode.

        Each device gets a hue offset by device_index * spread.

        Args:
            degrees_rotated: Total degrees of hue rotation
            device_index: Index of this device in participants list

        Returns:
            HSBK color for this device's frame
        """
        # Clamp device_index to available initial colors
        color_index = min(device_index, len(self._initial_colors) - 1)

        base_hue = self._initial_colors[color_index].hue
        device_spread_offset = (device_index * self.spread) % 360
        new_hue = round((base_hue + degrees_rotated + device_spread_offset) % 360)

        # Get brightness
        if self.brightness is not None:
            brightness = self.brightness
        else:
            brightness = self._initial_colors[color_index].brightness

        # Use consistent saturation for smooth animation
        saturation = (self.saturation_min + self.saturation_max) / 2

        # Use kelvin from initial color
        kelvin = self._initial_colors[color_index].kelvin

        return HSBK(
            hue=new_hue,
            saturation=saturation,
            brightness=brightness,
            kelvin=kelvin,
        )

    async def _get_initial_colors(self, participants: list[Light]) -> list[HSBK]:
        """Get initial colors for each participant.

        Args:
            participants: List of lights to get colors from

        Returns:
            List of HSBK colors, one per participant
        """

        async def get_color_for_light(light: Light) -> HSBK:
            """Get color for a single light."""
            # Determine fallback brightness based on effect configuration
            fallback_brightness = (
                self.brightness if self.brightness is not None else 0.8
            )

            # Use base class method for consistent color fetching with brightness safety
            return await self.fetch_light_color(
                light, fallback_brightness=fallback_brightness
            )

        # Fetch colors for all lights concurrently
        colors = await asyncio.gather(
            *(get_color_for_light(light) for light in participants)
        )

        return list(colors)

    async def from_poweroff_hsbk(self, _light: Light) -> HSBK:
        """Return startup color when light is powered off.

        For colorloop, start with random hue and target brightness.

        Args:
            _light: The device being powered on (unused)

        Returns:
            HSBK color to use as startup color
        """
        return HSBK(
            hue=random.randint(0, 360),
            saturation=random.uniform(self.saturation_min, self.saturation_max),
            brightness=self.brightness if self.brightness is not None else 0.8,
            kelvin=KELVIN_NEUTRAL,
        )

    def inherit_prestate(self, other: LIFXEffect) -> bool:
        """Colorloop can run without reset if switching to another colorloop.

        Args:
            other: The incoming effect

        Returns:
            True if other is also EffectColorloop, False otherwise
        """
        return isinstance(other, EffectColorloop)

    async def is_light_compatible(self, light: Light) -> bool:
        """Check if light is compatible with colorloop effect.

        Colorloop requires color capability to manipulate hue/saturation.

        Args:
            light: The light device to check

        Returns:
            True if light has color support, False otherwise
        """
        # Ensure capabilities are loaded
        if light.capabilities is None:
            await light.ensure_capabilities()

        # Check if light has color support
        return light.capabilities.has_color if light.capabilities else False

    def __repr__(self) -> str:
        """String representation of colorloop effect."""
        return (
            f"EffectColorloop(period={self.period}, change={self.change}, "
            f"spread={self.spread}, brightness={self.brightness}, "
            f"synchronized={self.synchronized}, power_on={self.power_on})"
        )
