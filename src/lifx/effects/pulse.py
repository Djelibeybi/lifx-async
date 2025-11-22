"""Pulse/blink/breathe effect implementation.

This module provides the EffectPulse class for creating various pulse effects.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from lifx.color import HSBK
from lifx.const import KELVIN_COOL, KELVIN_NEUTRAL
from lifx.effects.base import LIFXEffect
from lifx.effects.const import EFFECT_COMPLETION_BUFFER
from lifx.protocol.protocol_types import LightWaveform

if TYPE_CHECKING:
    from lifx.devices.light import Light

_LOGGER = logging.getLogger(__name__)

# Mode defaults
_MODE_DEFAULTS = {
    "blink": {
        "period": 1.0,
        "cycles": 1,
        "waveform": LightWaveform.PULSE,
    },
    "strobe": {
        "period": 0.1,
        "cycles": 10,
        "waveform": LightWaveform.PULSE,
    },
    "breathe": {
        "period": 1.0,
        "cycles": 1,
        "waveform": LightWaveform.SINE,
    },
    "ping": {
        "period": 1.0,
        "cycles": 1,
        "waveform": LightWaveform.PULSE,
    },
    "solid": {
        "period": 1.0,
        "cycles": 1,
        "waveform": LightWaveform.PULSE,
    },
}


class EffectPulse(LIFXEffect):
    """Pulse/blink/breathe effects using waveform modes.

    Supports multiple pulse modes: blink, strobe, breathe, ping, solid.
    Each mode has different timing defaults and waveform behavior.

    Attributes:
        mode: Pulse mode ('blink', 'strobe', 'breathe', 'ping', 'solid')
        period: Effect period in seconds
        cycles: Number of cycles to execute
        color: Optional color override
        waveform: Waveform type to use
        skew_ratio: Waveform skew ratio (0.0-1.0)

    Example:
        ```python
        # Blink effect
        effect = EffectPulse(mode="blink", cycles=5)
        await conductor.start(effect, [light])

        # Strobe with custom color
        effect = EffectPulse(mode="strobe", cycles=20, color=HSBK.from_rgb(255, 0, 0))
        await conductor.start(effect, [light])

        # Breathe effect
        effect = EffectPulse(mode="breathe", period=2.0, cycles=3)
        await conductor.start(effect, [light])
        ```
    """

    def __init__(
        self,
        power_on: bool = True,
        mode: str = "blink",
        period: float | None = None,
        cycles: int | None = None,
        color: HSBK | None = None,
    ) -> None:
        """Initialize pulse effect.

        Args:
            power_on: Power on devices if off (default True)
            mode: Pulse mode: 'blink', 'strobe', 'breathe', 'ping', 'solid'
                  (default 'blink')
            period: Effect period in seconds. Defaults depend on mode:
                    - strobe: 0.1s, others: 1.0s
            cycles: Number of cycles. Defaults:
                    - strobe: 10, others: 1
            color: Optional color override. If provided, this color
                   overrides the automatic color selection logic.

        Raises:
            ValueError: If mode is invalid
        """
        super().__init__(power_on=power_on)

        if mode not in _MODE_DEFAULTS:
            raise ValueError(
                f"Invalid mode '{mode}'. Must be one of: {list(_MODE_DEFAULTS.keys())}"
            )

        self.mode = mode
        defaults = _MODE_DEFAULTS[mode]

        self.period = period if period is not None else defaults["period"]
        self.cycles = cycles if cycles is not None else defaults["cycles"]
        self.color = color
        self.waveform = defaults["waveform"]

        # Ping and solid have special duty cycles
        if self.mode == "ping":
            ping_duration = int(5000 - min(2500, 300 * self.period))
            int_skew = 2**15 - ping_duration
            # Convert from int16 range (-32767 to 32767) to float (0.0 to 1.0)
            self.skew_ratio = (int_skew + 32767) / 65534
        elif self.mode == "solid":
            self.skew_ratio = 0.0
        else:
            self.skew_ratio = 0.5

        # Validate parameters
        if self.period <= 0:
            raise ValueError(f"Period must be positive, got {self.period}")
        if self.cycles < 1:
            raise ValueError(f"Cycles must be 1 or higher, got {self.cycles}")

    @property
    def name(self) -> str:
        """Return the name of the effect.

        Returns:
            The effect name 'pulse'
        """
        return "pulse"

    async def async_play(self) -> None:
        """Execute the pulse effect on all participants."""
        # Determine colors for each light
        colors = await self._get_colors()

        # Apply waveform to all lights concurrently
        tasks = []
        for light, color in zip(self.participants, colors):
            tasks.append(self._apply_waveform(light, color))

        await asyncio.gather(*tasks)

        # Wait for effects to complete
        total_duration = self.period * self.cycles
        await asyncio.sleep(total_duration + EFFECT_COMPLETION_BUFFER)  # Small buffer

    async def _get_colors(self) -> list[HSBK]:
        """Determine colors for each participant light.

        Returns:
            List of HSBK colors, one per participant
        """

        async def get_color_for_light(light: Light) -> HSBK:
            """Get color for a single light."""
            # If user provided explicit color, use it
            if self.color is not None:
                return self.color

            # Otherwise, intelligently select color based on mode and device
            if self.mode == "strobe":
                # Strobe pulses to full brightness cold white
                return HSBK(hue=0, saturation=0, brightness=1.0, kelvin=KELVIN_COOL)
            else:
                # Use base class method for consistent color fetching with
                # brightness safety
                return await self.fetch_light_color(light)

        # Fetch colors for all lights concurrently
        colors: list[HSBK] = [None] * len(self.participants)  # type: ignore

        async with asyncio.TaskGroup() as tg:
            for idx, light in enumerate(self.participants):

                async def fetch_and_store(index: int, device: Light) -> None:
                    colors[index] = await get_color_for_light(device)

                tg.create_task(fetch_and_store(idx, light))

        return colors

    async def _apply_waveform(self, light: Light, color: HSBK) -> None:
        """Apply waveform to a single light.

        Args:
            light: Light device to apply waveform to
            color: Color to use for waveform
        """
        try:
            await light.set_waveform(
                color=color,
                period=self.period,
                cycles=self.cycles,
                waveform=self.waveform,
                transient=True,
                skew_ratio=self.skew_ratio,
            )
        except Exception as e:
            _LOGGER.error(
                {
                    "class": self.__class__.__name__,
                    "method": "_apply_waveform",
                    "action": "change",
                    "error": str(e),
                    "values": {
                        "serial": light.serial,
                        "mode": self.mode,
                        "period": self.period,
                        "cycles": self.cycles,
                        "color": {
                            "hue": color.hue,
                            "saturation": color.saturation,
                            "brightness": color.brightness,
                            "kelvin": color.kelvin,
                        },
                    },
                }
            )

    async def from_poweroff_hsbk(self, _light: Light) -> HSBK:
        """Return startup color when light is powered off.

        For pulse effects, we want a sensible startup color based on mode.

        Args:
            _light: The device being powered on (unused)

        Returns:
            HSBK color to use as startup color
        """
        if self.color is not None:
            # Use user-specified color with zero brightness
            return self.color.with_brightness(0.0)

        if self.mode == "strobe":
            # Strobe starts from dark cold white
            return HSBK(hue=0, saturation=0, brightness=0, kelvin=KELVIN_COOL)
        else:
            # Other modes start from neutral white with zero brightness
            return HSBK(hue=0, saturation=0, brightness=0, kelvin=KELVIN_NEUTRAL)

    def __repr__(self) -> str:
        """String representation of pulse effect."""
        return (
            f"EffectPulse(mode={self.mode}, period={self.period}, "
            f"cycles={self.cycles}, power_on={self.power_on})"
        )
