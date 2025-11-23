"""Light device class for LIFX color lights."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

from lifx.color import HSBK
from lifx.const import (
    MAX_BRIGHTNESS,
    MAX_HUE,
    MAX_KELVIN,
    MAX_SATURATION,
    MIN_BRIGHTNESS,
    MIN_HUE,
    MIN_KELVIN,
    MIN_SATURATION,
)
from lifx.devices.base import (
    Device,
    DeviceState,
)
from lifx.exceptions import LifxError, LifxTimeoutError
from lifx.protocol import packets
from lifx.protocol.protocol_types import LightWaveform

if TYPE_CHECKING:
    from lifx.theme import Theme

_LOGGER = logging.getLogger(__name__)


@dataclass
class LightState(DeviceState):
    """Light device state with color control.

    Attributes:
        color: Current HSBK color
    """

    color: HSBK

    @property
    def as_dict(self) -> Any:
        """Return LightState as a dict."""
        return asdict(self)


class Light(Device[LightState]):
    """LIFX light device with color control.

    Extends the base Device class with light-specific functionality:
    - Color control (HSBK)
    - Brightness control
    - Color temperature control
    - Waveform effects

    Example:
        ```python
        light = Light(serial="d073d5123456", ip="192.168.1.100")

        async with light:
            # Set color
            await light.set_color(HSBK.from_rgb(255, 0, 0))

            # Set brightness
            await light.set_brightness(0.5)

            # Set temperature
            await light.set_temperature(3500)
        ```

        Using the simplified connect method (without knowing the serial):
        ```python
        async with await Light.from_ip(ip="192.168.1.100") as light:
            await light.set_color(HSBK.from_rgb(255, 0, 0))
        ```
    """

    def __init__(self, *args, **kwargs) -> None:
        """Initialize Light with additional state attributes."""
        super().__init__(*args, **kwargs)

    @property
    def state(self) -> LightState:
        """Get light state (guaranteed to be initialized when using Device.connect()).

        Returns:
            LightState with current light state

        Raises:
            RuntimeError: If accessed before state initialization
        """
        if self._state is None:
            raise RuntimeError("State not found.")
        return self._state

    async def get_color(self) -> tuple[HSBK, int, str]:
        """Get current light color, power, and label.

        Always fetches from device. Use the `color` property to access stored value.

        Returns a tuple containing:
        - color: HSBK color
        - power: Power level as integer (0 for off, 65535 for on)
        - label: Device label/name

        Returns:
            Tuple of (color, power, label)

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxProtocolError: If response is invalid
            LifxUnsupportedCommandError: If device doesn't support this command

        Example:
            ```python
            color, power, label = await light.get_color()
            print(f"{label}: Hue: {color.hue}°, Power: {'ON' if power > 0 else 'OFF'}")
            ```
        """
        # Request automatically unpacks response and decodes labels
        state = await self.connection.request(packets.Light.GetColor())
        self._raise_if_unhandled(state)

        # Convert from protocol HSBK to user-friendly HSBK
        color = HSBK.from_protocol(state.color)
        power = state.power
        label = state.label

        # Store label from StateColor response
        self._label = label  # Already decoded to string

        # Update state if it exists (including all subclasses)
        if self._state is not None:
            # Update base fields available on all device states
            self._state.power = power
            self._state.label = label

            if hasattr(self._state, "color"):
                self._state.color = color

            self._state.last_updated = __import__("time").time()

        _LOGGER.debug(
            {
                "class": "Device",
                "method": "get_color",
                "action": "query",
                "reply": {
                    "hue": state.color.hue,
                    "saturation": state.color.saturation,
                    "brightness": state.color.brightness,
                    "kelvin": state.color.kelvin,
                    "power": state.power,
                    "label": state.label,
                },
            }
        )

        return color, power, label

    async def set_color(
        self,
        color: HSBK,
        duration: float = 0.0,
    ) -> None:
        """Set light color.

        Args:
            color: HSBK color to set
            duration: Transition duration in seconds (default 0.0)

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxUnsupportedCommandError: If device doesn't support this command

        Example:
            ```python
            # Set to red instantly
            await light.set_color(HSBK.from_rgb(255, 0, 0))

            # Fade to blue over 2 seconds
            await light.set_color(HSBK.from_rgb(0, 0, 255), duration=2.0)
            ```
        """
        # Convert to protocol HSBK
        protocol_color = color.to_protocol()

        # Convert duration to milliseconds
        duration_ms = int(duration * 1000)

        # Request automatically handles acknowledgement
        result = await self.connection.request(
            packets.Light.SetColor(
                color=protocol_color,
                duration=duration_ms,
            ),
        )
        self._raise_if_unhandled(result)

        _LOGGER.debug(
            {
                "class": "Light",
                "method": "set_color",
                "action": "change",
                "values": {
                    "hue": protocol_color.hue,
                    "saturation": protocol_color.saturation,
                    "brightness": protocol_color.brightness,
                    "kelvin": protocol_color.kelvin,
                    "duration": duration_ms,
                },
            }
        )

        # Update state on acknowledgement
        if result and self._state is not None:
            self._state.color = color
            await self._schedule_refresh()

    async def set_brightness(self, brightness: float, duration: float = 0.0) -> None:
        """Set light brightness only, preserving hue, saturation, and temperature.

        Args:
            brightness: Brightness level (0.0-1.0)
            duration: Transition duration in seconds (default 0.0)

        Raises:
            ValueError: If brightness is out of range
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond

        Example:
            ```python
            # Set to 50% brightness
            await light.set_brightness(0.5)

            # Fade to full brightness over 1 second
            await light.set_brightness(1.0, duration=1.0)
            ```
        """
        if not (MIN_BRIGHTNESS <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(
                f"Brightness must be between {MIN_BRIGHTNESS} "
                f"and {MAX_BRIGHTNESS}, got {brightness}"
            )

        # Use set_waveform_optional with HALF_SINE waveform to set brightness
        # without needing to query current color values. Convert duration to seconds.
        color = HSBK(hue=0, saturation=0, brightness=brightness, kelvin=3500)

        await self.set_waveform_optional(
            color=color,
            period=max(duration, 0.001),
            cycles=1,
            waveform=LightWaveform.HALF_SINE,
            transient=False,
            set_hue=False,
            set_saturation=False,
            set_brightness=True,
            set_kelvin=False,
        )

    async def set_kelvin(self, kelvin: int, duration: float = 0.0) -> None:
        """Set light color temperature, preserving brightness. Saturation is
           automatically set to 0 to switch the light to color temperature mode.

        Args:
            kelvin: Color temperature in Kelvin (1500-9000)
            duration: Transition duration in seconds (default 0.0)

        Raises:
            ValueError: If kelvin is out of range
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond

        Example:
            ```python
            # Set to warm white
            await light.set_kelvin(2500)

            # Fade to cool white over 2 seconds
            await light.set_kelvin(6500, duration=2.0)
            ```
        """
        if not (MIN_KELVIN <= kelvin <= MAX_KELVIN):
            raise ValueError(
                f"Kelvin must be between {MIN_KELVIN} and {MAX_KELVIN}, got {kelvin}"
            )

        # Use set_waveform_optional with HALF_SINE waveform to set kelvin
        # and saturation without needing to query current color values
        color = HSBK(hue=0, saturation=0, brightness=1.0, kelvin=kelvin)

        await self.set_waveform_optional(
            color=color,
            period=max(duration, 0.001),
            cycles=1,
            waveform=LightWaveform.HALF_SINE,
            transient=False,
            set_hue=False,
            set_saturation=True,
            set_brightness=False,
            set_kelvin=True,
        )

    async def set_hue(self, hue: int, duration: float = 0.0) -> None:
        """Set light hue only, preserving saturation, brightness, and temperature.

        Args:
            hue: Hue in degrees (0-360)
            duration: Transition duration in seconds (default 0.0)

        Raises:
            ValueError: If hue is out of range
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond

        Example:
            ```python
            # Set to red (0 degrees)
            await light.set_hue(0)

            # Cycle through rainbow
            for hue in range(0, 360, 10):
                await light.set_hue(hue, duration=0.5)
            ```
        """
        if not (MIN_HUE <= hue <= MAX_HUE):
            raise ValueError(f"Hue must be between {MIN_HUE} and {MAX_HUE}, got {hue}")

        # Use set_waveform_optional with HALF_SINE waveform to set hue
        # without needing to query current color values
        color = HSBK(hue=hue, saturation=1.0, brightness=1.0, kelvin=3500)

        await self.set_waveform_optional(
            color=color,
            period=max(duration, 0.001),
            cycles=1,
            waveform=LightWaveform.HALF_SINE,
            transient=False,
            set_hue=True,
            set_saturation=False,
            set_brightness=False,
            set_kelvin=False,
        )

    async def set_saturation(self, saturation: float, duration: float = 0.0) -> None:
        """Set light saturation only, preserving hue, brightness, and temperature.

        Args:
            saturation: Saturation level (0.0-1.0)
            duration: Transition duration in seconds (default 0.0)

        Raises:
            ValueError: If saturation is out of range
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond

        Example:
            ```python
            # Set to fully saturated
            await light.set_saturation(1.0)

            # Fade to white (no saturation) over 2 seconds
            await light.set_saturation(0.0, duration=2.0)
            ```
        """
        if not (MIN_SATURATION <= saturation <= MAX_SATURATION):
            raise ValueError(
                f"Saturation must be between {MIN_SATURATION} "
                f"and {MAX_SATURATION}, got {saturation}"
            )

        # Use set_waveform_optional with HALF_SINE waveform to set saturation
        # without needing to query current color values
        color = HSBK(hue=0, saturation=saturation, brightness=1.0, kelvin=3500)

        await self.set_waveform_optional(
            color=color,
            period=max(duration, 0.001),
            cycles=1,
            waveform=LightWaveform.HALF_SINE,
            transient=False,
            set_hue=False,
            set_saturation=True,
            set_brightness=False,
            set_kelvin=False,
        )

    async def get_power(self) -> int:
        """Get light power state (specific to light, not device).

        Always fetches from device.

        This overrides Device.get_power() as it queries the light-specific
        power state (packet type 116/118) instead of device power (packet type 20/22).

        Returns:
            Power level as integer (0 for off, 65535 for on)

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxProtocolError: If response is invalid
            LifxUnsupportedCommandError: If device doesn't support this command

        Example:
            ```python
            level = await light.get_power()
            print(f"Light power: {'ON' if level > 0 else 'OFF'}")
            ```
        """
        # Request automatically unpacks response
        state = await self.connection.request(packets.Light.GetPower())
        self._raise_if_unhandled(state)

        # Power level is uint16 (0 or 65535)
        _LOGGER.debug(
            {
                "class": "Device",
                "method": "get_power",
                "action": "query",
                "reply": {"level": state.level},
            }
        )

        return state.level

    async def get_ambient_light_level(self) -> float:
        """Get ambient light level from device sensor.

        Always fetches from device (volatile property, not cached).

        This method queries the device's ambient light sensor to get the current
        lux reading. Devices without ambient light sensors will return 0.0.

        Returns:
            Ambient light level in lux (0.0 if device has no sensor)

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxProtocolError: If response is invalid
            LifxUnsupportedCommandError: If device doesn't support this command

        Example:
            ```python
            lux = await light.get_ambient_light_level()
            if lux > 0:
                print(f"Ambient light: {lux} lux")
            else:
                print("No ambient light sensor or completely dark")
            ```
        """
        # Request automatically unpacks response
        state = await self.connection.request(packets.Sensor.GetAmbientLight())
        self._raise_if_unhandled(state)

        _LOGGER.debug(
            {
                "class": "Light",
                "method": "get_ambient_light_level",
                "action": "query",
                "reply": {"lux": state.lux},
            }
        )

        return state.lux

    async def set_power(self, level: bool | int, duration: float = 0.0) -> None:
        """Set light power state (specific to light, not device).

        This overrides Device.set_power() as it uses the light-specific
        power packet (type 117) which supports transition duration.

        Args:
            level: True/65535 to turn on, False/0 to turn off
            duration: Transition duration in seconds (default 0.0)

        Raises:
            ValueError: If integer value is not 0 or 65535
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxUnsupportedCommandError: If device doesn't support this command

        Example:
            ```python
            # Turn on instantly with boolean
            await light.set_power(True)

            # Turn on with integer
            await light.set_power(65535)

            # Fade off over 3 seconds
            await light.set_power(False, duration=3.0)
            await light.set_power(0, duration=3.0)
            ```
        """
        # Power level: 0 for off, 65535 for on
        if isinstance(level, bool):
            power_level = 65535 if level else 0
        elif isinstance(level, int):
            if level not in (0, 65535):
                raise ValueError(f"Power level must be 0 or 65535, got {level}")
            power_level = level
        else:
            raise TypeError(f"Expected bool or int, got {type(level).__name__}")

        # Convert duration to milliseconds
        duration_ms = int(duration * 1000)

        # Request automatically handles acknowledgement
        result = await self.connection.request(
            packets.Light.SetPower(level=power_level, duration=duration_ms),
        )
        self._raise_if_unhandled(result)

        _LOGGER.debug(
            {
                "class": "Light",
                "method": "set_power",
                "action": "change",
                "values": {"level": power_level, "duration": duration_ms},
            }
        )

        # Update state on acknowledgement
        if result and self._state is not None:
            self._state.power = power_level

        # Schedule refresh to validate state
        if self._state is not None:
            await self._schedule_refresh()

    async def set_waveform(
        self,
        color: HSBK,
        period: float,
        cycles: float,
        waveform: LightWaveform,
        transient: bool = True,
        skew_ratio: float = 0.5,
    ) -> None:
        """Apply a waveform effect to the light.

        Waveforms create repeating color transitions. Useful for effects like
        pulsing, breathing, or blinking.

        Args:
            color: Target color for the waveform
            period: Period of one cycle in seconds
            cycles: Number of cycles
            waveform: Waveform type (SAW, SINE, HALF_SINE, TRIANGLE, PULSE)
            transient: If True, return to original color after effect (default True)
            skew_ratio: Waveform skew (0.0-1.0, default 0.5 for symmetric)

        Raises:
            ValueError: If parameters are out of range
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxUnsupportedCommandError: If device doesn't support this command

        Example:
            ```python
            from lifx.protocol.protocol_types import LightWaveform

            # Pulse red 5 times
            await light.set_waveform(
                color=HSBK.from_rgb(255, 0, 0),
                period=1.0,
                cycles=5,
                waveform=LightWaveform.SINE,
            )

            # Breathe white once
            await light.set_waveform(
                color=HSBK(0, 0, 1.0, 3500),
                period=2.0,
                cycles=1,
                waveform=LightWaveform.SINE,
                transient=False,
            )
            ```
        """
        if period <= 0:
            raise ValueError(f"Period must be positive, got {period}")
        if cycles < 1:
            raise ValueError(f"Cycles must be 1 or higher, got {cycles}")
        if not (0.0 <= skew_ratio <= 1.0):
            raise ValueError(
                f"Skew ratio must be between 0.0 and 1.0, got {skew_ratio}"
            )

        # Convert to protocol values
        protocol_color = color.to_protocol()
        period_ms = int(period * 1000)
        skew_ratio_i16 = int(skew_ratio * 65535) - 32768  # Convert to int16 range

        # Send request
        result = await self.connection.request(
            packets.Light.SetWaveform(
                transient=bool(transient),
                color=protocol_color,
                period=period_ms,
                cycles=cycles,
                skew_ratio=skew_ratio_i16,
                waveform=waveform,
            ),
        )
        self._raise_if_unhandled(result)
        _LOGGER.debug(
            {
                "class": "Device",
                "method": "set_waveform",
                "action": "change",
                "values": {
                    "transient": transient,
                    "hue": protocol_color.hue,
                    "saturation": protocol_color.saturation,
                    "brightness": protocol_color.brightness,
                    "kelvin": protocol_color.kelvin,
                    "period": period_ms,
                    "cycles": cycles,
                    "skew_ratio": skew_ratio_i16,
                    "waveform": waveform.value,
                },
            }
        )

        # Schedule refresh to update state
        if self._state is not None:
            await self._schedule_refresh()

    async def set_waveform_optional(
        self,
        color: HSBK,
        period: float,
        cycles: float,
        waveform: LightWaveform,
        transient: bool = True,
        skew_ratio: float = 0.5,
        set_hue: bool = True,
        set_saturation: bool = True,
        set_brightness: bool = True,
        set_kelvin: bool = True,
    ) -> None:
        """Apply a waveform effect with selective color component control.

        Similar to set_waveform() but allows fine-grained control over which
        color components (hue, saturation, brightness, kelvin) are affected
        by the waveform. This enables effects like pulsing brightness while
        keeping hue constant, or cycling hue while maintaining brightness.

        Args:
            color: Target color for the waveform
            period: Period of one cycle in seconds
            cycles: Number of cycles
            waveform: Waveform type (SAW, SINE, HALF_SINE, TRIANGLE, PULSE)
            transient: If True, return to original color after effect (default True)
            skew_ratio: Waveform skew (0.0-1.0, default 0.5 for symmetric)
            set_hue: Apply waveform to hue component (default True)
            set_saturation: Apply waveform to saturation component (default True)
            set_brightness: Apply waveform to brightness component (default True)
            set_kelvin: Apply waveform to kelvin component (default True)

        Raises:
            ValueError: If parameters are out of range
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxUnsupportedCommandError: If device doesn't support this command

        Example:
            ```python
            from lifx.protocol.protocol_types import LightWaveform

            # Pulse brightness only, keeping hue/saturation constant
            await light.set_waveform_optional(
                color=HSBK(0, 1.0, 1.0, 3500),
                period=1.0,
                cycles=5,
                waveform=LightWaveform.SINE,
                set_hue=False,
                set_saturation=False,
                set_brightness=True,
                set_kelvin=False,
            )

            # Cycle hue while maintaining brightness
            await light.set_waveform_optional(
                color=HSBK(180, 1.0, 1.0, 3500),
                period=5.0,
                cycles=0,  # Infinite
                waveform=LightWaveform.SAW,
                set_hue=True,
                set_saturation=False,
                set_brightness=False,
                set_kelvin=False,
            )
            ```
        """
        if period <= 0:
            raise ValueError(f"Period must be positive, got {period}")
        if cycles < 0:
            raise ValueError(f"Cycles must be non-negative, got {cycles}")
        if not (0.0 <= skew_ratio <= 1.0):
            raise ValueError(
                f"Skew ratio must be between 0.0 and 1.0, got {skew_ratio}"
            )

        # Convert to protocol values
        protocol_color = color.to_protocol()
        period_ms = int(period * 1000)
        skew_ratio_i16 = int(skew_ratio * 65535) - 32768  # Convert to int16 range

        # Send request
        result = await self.connection.request(
            packets.Light.SetWaveformOptional(
                transient=bool(transient),
                color=protocol_color,
                period=period_ms,
                cycles=cycles,
                skew_ratio=skew_ratio_i16,
                waveform=waveform,
                set_hue=set_hue,
                set_saturation=set_saturation,
                set_brightness=set_brightness,
                set_kelvin=set_kelvin,
            ),
        )
        self._raise_if_unhandled(result)
        _LOGGER.debug(
            {
                "class": "Light",
                "method": "set_waveform_optional",
                "action": "change",
                "values": {
                    "transient": transient,
                    "hue": protocol_color.hue,
                    "saturation": protocol_color.saturation,
                    "brightness": protocol_color.brightness,
                    "kelvin": protocol_color.kelvin,
                    "period": period_ms,
                    "cycles": cycles,
                    "skew_ratio": skew_ratio_i16,
                    "waveform": waveform.value,
                    "set_hue": set_hue,
                    "set_saturation": set_saturation,
                    "set_brightness": set_brightness,
                    "set_kelvin": set_kelvin,
                },
            }
        )

        # Update state on acknowledgement (only if non-transient)
        if result and not transient and self._state is not None:
            # Create a new color with only the specified components updated
            current = self._state.color
            new_color = HSBK(
                hue=color.hue if set_hue else current.hue,
                saturation=color.saturation if set_saturation else current.saturation,
                brightness=color.brightness if set_brightness else current.brightness,
                kelvin=color.kelvin if set_kelvin else current.kelvin,
            )
            self._state.color = new_color

        # Schedule refresh to validate state
        if self._state is not None:
            await self._schedule_refresh()

    async def pulse(
        self,
        color: HSBK,
        period: float = 1.0,
        cycles: float = 1,
        transient: bool = True,
    ) -> None:
        """Pulse the light to a specific color.

        Convenience method for creating a pulse effect using SINE waveform.

        Args:
            color: Target color to pulse to
            period: Period of one pulse in seconds (default 1.0)
            cycles: Number of pulses (default 1)
            transient: If True, return to original color after effect (default True)

        Example:
            ```python
            # Pulse red once
            await light.pulse(HSBK.from_rgb(255, 0, 0))

            # Pulse blue 3 times, 2 seconds per pulse
            await light.pulse(HSBK.from_rgb(0, 0, 255), period=2.0, cycles=3)
            ```
        """
        await self.set_waveform(
            color=color,
            period=period,
            cycles=cycles,
            waveform=LightWaveform.PULSE,
            transient=transient,
        )

    async def breathe(
        self,
        color: HSBK,
        period: float = 2.0,
        cycles: float = 1,
    ) -> None:
        """Make the light breathe to a specific color.

        Convenience method for creating a breathing effect using SINE waveform.

        Args:
            color: Target color to breathe to
            period: Period of one breath in seconds (default 2.0)
            cycles: Number of breaths (default 1)

        Example:
            ```python
            # Breathe white once
            await light.breathe(HSBK(0, 0, 1.0, 3500))

            # Breathe purple 10 times
            await light.breathe(HSBK.from_rgb(128, 0, 128), cycles=10)
            ```
        """
        await self.set_waveform(
            color=color,
            period=period,
            cycles=cycles,
            waveform=LightWaveform.SINE,
            transient=True,
        )

    # Cached value properties
    @property
    def min_kelvin(self) -> int | None:
        """Get the minimum supported kelvin value if available.

        Returns:
            Minimum kelvin value from product registry.
        """
        if (
            self.capabilities is not None
            and self.capabilities.temperature_range is not None
        ):
            return self.capabilities.temperature_range.min

        return None

    @property
    def max_kelvin(self) -> int | None:
        """Get the maximum supported kelvin value if available.

        Returns:
            Maximum kelvin value from product registry.
        """
        if (
            self.capabilities is not None
            and self.capabilities.temperature_range is not None
        ):
            return self.capabilities.temperature_range.max

        return None

    async def apply_theme(
        self,
        theme: Theme,
        power_on: bool = False,
        duration: float = 0.0,
    ) -> None:
        """Apply a theme to this light.

        Selects a random color from the theme and applies it to the light.

        Args:
            theme: Theme to apply
            power_on: Turn on the light
            duration: Transition duration in seconds

        Example:
            ```python
            from lifx.theme import get_theme

            theme = get_theme("evening")
            await light.apply_theme(theme, power_on=True, duration=0.5)
            ```
        """
        if self.capabilities is None:
            await self._ensure_capabilities()

        if self.capabilities and not self.capabilities.has_color:
            return

        # Select a random color from theme
        color = theme.random()

        # Check if light is on
        is_on = await self.get_power()

        # Apply color to light
        # If light is off and we're turning it on, set color immediately then fade on
        if power_on and not is_on:
            await self.set_color(color, duration=0)
            await self.set_power(True, duration=duration)
        else:
            # Light is already on, or we're not turning it on - apply with duration
            await self.set_color(color, duration=duration)

    def __repr__(self) -> str:
        """String representation of light."""
        return f"Light(serial={self.serial}, ip={self.ip}, port={self.port})"

    async def refresh_state(self) -> None:
        """Refresh light state from hardware.

        Fetches color (which includes power and label) and updates state.

        Raises:
            RuntimeError: If state has not been initialized
            LifxTimeoutError: If device does not respond
            LifxDeviceNotFoundError: If device cannot be reached
        """
        import time

        if self._state is None:
            await self._initialize_state()
            return

        # GetColor returns color, power, and label in one request
        color, power, label = await self.get_color()

        self._state.color = color
        self._state.power = power
        self._state.label = label
        self._state.last_updated = time.time()

    async def _initialize_state(self) -> LightState:
        """Initialize light state transactionally.

        Extends base implementation to fetch color in addition to base state.

        Args:
            timeout: Timeout for state initialization

        Raises:
            LifxTimeoutError: If device does not respond within timeout
            LifxDeviceNotFoundError: If device cannot be reached
            LifxProtocolError: If responses are invalid
        """
        import time

        # Ensure capabilities are loaded
        await self._ensure_capabilities()
        capabilities = self._create_capabilities()

        # Fetch semi-static and volatile state in parallel
        # get_color returns color, power, and label in one request
        try:
            async with asyncio.TaskGroup() as tg:
                color_task = tg.create_task(self.get_color())
                host_fw_task = tg.create_task(self.get_host_firmware())
                wifi_fw_task = tg.create_task(self.get_wifi_firmware())
                location_task = tg.create_task(self.get_location())
                group_task = tg.create_task(self.get_group())

            # Extract results
            color, power, label = color_task.result()
            host_firmware = host_fw_task.result()
            wifi_firmware = wifi_fw_task.result()
            location_info = location_task.result()
            group_info = group_task.result()

            # Get MAC address (already calculated in get_host_firmware)
            mac_address = await self.get_mac_address()

            # Get model name
            assert self._capabilities is not None
            model = self._capabilities.name

            # Create state instance with color
            self._state = LightState(
                model=model,
                label=label,
                serial=self.serial,
                mac_address=mac_address,
                capabilities=capabilities,
                power=power,
                host_firmware=host_firmware,
                wifi_firmware=wifi_firmware,
                location=location_info,
                group=group_info,
                color=color,
                last_updated=time.time(),
            )

            return self._state

        except* LifxTimeoutError:
            raise LifxTimeoutError(f"Error initializing state for {self.serial}")
        except* LifxError:
            raise LifxError(f"Error initializing state for {self.serial}")
