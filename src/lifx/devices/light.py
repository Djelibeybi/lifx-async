"""Light device class for LIFX color lights."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

from lifx.animation.animator import Animator
from lifx.animation.framebuffer import FrameBuffer
from lifx.animation.packets import LightPacketGenerator, PacketGenerator
from lifx.color import HSBK
from lifx.const import (
    INVALID_AMBIENT_LIGHT_RESPONSE,
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
    WifiInfo,
)
from lifx.devices.effect_runner import effect_runner
from lifx.exceptions import LifxError, LifxTimeoutError
from lifx.protocol import packets
from lifx.protocol.protocol_types import LightWaveform

if TYPE_CHECKING:
    from lifx.effects.base import LIFXEffect
    from lifx.theme import Theme

_LOGGER = logging.getLogger(__name__)


@dataclass
class LightState(DeviceState):
    """Light device state with color control.

    Attributes:
        color: Current HSBK color
        ambient_light: Ambient light level in lux, or None when the sensor was
            not queried. Devices without a sensor report 0.0, as does a device
            in complete darkness. A reading taken while the light is on measures
            the light's own output rather than the room, and is stored as
            :data:`~lifx.const.INVALID_AMBIENT_LIGHT_RESPONSE` (-1.0) to mark it
            unusable. Keyword-only with a default so adding it stays additive
            for existing constructors.
    """

    color: HSBK
    ambient_light: float | None = field(kw_only=True, default=None)

    @property
    def as_dict(self) -> Any:
        """Return LightState as a dict.

        Extends :attr:`DeviceState.as_dict` so the curated capability and
        firmware expansion applies to light states too. HSBK is not a
        dataclass, so ``color`` is expanded via :attr:`HSBK.as_dict` to keep
        the result serialisable.

        Subclasses extend this and add their own fields explicitly rather than
        calling ``dataclasses.asdict``, which would both bypass that curation
        and deep-copy every HSBK just for the override to discard it.
        """
        state: dict[str, Any] = super().as_dict
        state["color"] = self.color.as_dict
        state["ambient_light"] = self.ambient_light
        return state


@dataclass(frozen=True)
class _DiscoveryLightSnapshot:
    """Immutable colour, power, and label adopted during discovery."""

    colour: HSBK
    power: int
    label: str


class Light(Device[LightState]):
    """LIFX light device with color control.

    Extends the base Device class with light-specific functionality:

    - Color control (HSBK)
    - Brightness control
    - Color temperature control
    - Waveform control

    Example:
        ```python
        light = Light(serial="d073d5123456", ip="192.168.1.100")

        async with light:
            # Set color
            await light.set_color(HSBK.from_rgb(1.0, 0.0, 0.0))

            # Set brightness
            await light.set_brightness(0.5)

            # Set temperature
            await light.set_temperature(3500)
        ```

        Using the simplified connect method (without knowing the serial):
        ```python
        async with await Device.connect(ip="192.168.1.100") as light:
            await light.set_color(HSBK.from_rgb(1.0, 0.0, 0.0))
        ```
    """

    _discovery_snapshot: _DiscoveryLightSnapshot | None = None
    _animator: Animator | None = None

    @property
    def animator(self) -> Animator:
        """The one Animator this light owns, created on first access.

        Library effects and direct frame senders such as LedFx borrow this
        Animator, so every frame for the light goes through one writer and
        one ack gate. A single light's Animator is ready at once; a matrix or
        multizone light's Animator must be prepared before its first frame,
        which queries the device for its geometry once.

        Example:
            ```python
            async with await Device.connect("192.0.2.10") as device:
                animator = await device.animator.prepare()

            while running:
                animator.send_frame(frame)
                await asyncio.sleep(1 / 30)
            ```
        """
        animator = self._animator
        if animator is None:
            animator = Animator._for_device(self)
            self._animator = animator
        return animator

    def _animation_geometry(self) -> tuple[FrameBuffer, PacketGenerator] | None:
        """The canvas and packets this light's Animator draws with, if known.

        A single light needs no query: it is one pixel. A matrix or multizone
        light returns None, and its Animator asks it with
        ``_query_animation_geometry()`` when first prepared.
        """
        return FrameBuffer.for_light(self), LightPacketGenerator()

    async def _query_animation_geometry(
        self,
    ) -> tuple[FrameBuffer, PacketGenerator]:
        """Ask the device for the geometry its Animator draws with.

        A single light knows its geometry without asking.
        """
        geometry = self._animation_geometry()
        assert geometry is not None
        return geometry

    async def start_effect(
        self, effect: LIFXEffect, *, enable_thread: bool = False
    ) -> None:
        """Start a software effect on this light alone.

        A shortcut for a one-participant Conductor run: the light's prior
        state is captured before the effect starts and restored when it ends
        or when ``stop_effect()`` is called. Each light keeps one Conductor
        for these runs, so starting another effect on the same light follows
        the Conductor's rules: it replaces the running effect and inherits
        its original prior state. On a Ceiling or Mirror it also replaces any
        effects on the light components, and stopping it restores what was
        there before any of them started.

        Only software effects can be started here. Firmware effects keep
        their own API, such as ``set_effect()`` on matrix and multizone
        lights.

        An effect that draws frames streams them to the light, and a Thread
        mesh is not built for that traffic. On a light evidenced as Thread,
        by its own replies or an mDNS record, it is refused unless
        ``enable_thread`` is True. A light not yet heard from is not refused,
        and neither is an effect that draws no frames, such as EffectPulse.

        Args:
            effect: The software effect to run
            enable_thread: Stream frames to a light evidenced as Thread
                anyway. Off by default.

        Raises:
            TypeError: If ``effect`` is not a software effect
            LifxUnsupportedCommandError: If the effect draws frames, the
                light is evidenced as Thread and ``enable_thread`` is False

        Example:
            ```python
            from lifx.effects import EffectColorloop

            await light.start_effect(EffectColorloop())
            await asyncio.sleep(10)
            await light.stop_effect()
            ```
        """
        await effect_runner().start(self, effect, enable_thread=enable_thread)

    async def stop_effect(self) -> None:
        """Stop every effect on this light.

        Stops any running firmware effect, then any software effect the light
        or one of its light components is part of, and restores the prior
        state of each. The software effect
        may have been started with ``start_effect()`` or on any Conductor: if
        the light is one participant of a multi-light run, it leaves that run
        and the other participants carry on.

        Example:
            ```python
            await light.stop_effect()
            ```
        """
        try:
            await self._stop_firmware_effect()
        finally:
            await effect_runner().leave_every_run(self)

    async def _stop_firmware_effect(self) -> None:
        """Stop a running firmware effect; a plain light has none to stop."""

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

    def _adopt_state_color(
        self, state: packets.Light.StateColor
    ) -> tuple[HSBK, int, str]:
        """Decode and adopt a validated StateColor response."""
        colour = HSBK.from_protocol(state.color)
        power = state.power
        # DeviceConnection decodes protocol labels before returning packets.
        label = cast(str, state.label)

        self._label = label
        self._discovery_snapshot = _DiscoveryLightSnapshot(
            colour=colour,
            power=power,
            label=label,
        )

        if self._state is not None:
            self._state.power = power
            self._state.label = label

            if hasattr(self._state, "color"):
                self._state.color = colour

            self._state.last_updated = time.time()

        return colour, power, label

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

        color, power, label = self._adopt_state_color(state)

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
            await light.set_color(HSBK.from_rgb(1.0, 0.0, 0.0))

            # Fade to blue over 2 seconds
            await light.set_color(HSBK.from_rgb(0.0, 0.0, 1.0), duration=2.0)
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
        self._zones_changed()

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

    def _zones_changed(self) -> None:
        """Hook called after a write that changes zone colours.

        A no-op here. Component devices override it to forget colours they
        were tracking for an in-flight transition, so a later component write
        does not undo a colour change made through an inherited method.
        """

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
        """Apply a waveform to the light.

        Waveforms create repeating color transitions. Useful for pulsing,
        breathing, or blinking.

        Cycles may be fractional; 0.5 is a half cycle. On a colour bulb, a
        half cycle moves towards the target for half a period, then a
        transient waveform jumps straight back to the original colour
        (no fade back), while a non-transient one stays at the target.

        Args:
            color: Target color for the waveform
            period: Period of one cycle in seconds. Zero requests an immediate
                transition.
            cycles: Number of cycles, must be greater than 0 (may be fractional)
            waveform: Waveform type (SAW, SINE, HALF_SINE, TRIANGLE, PULSE)
            transient: If True, return to the original color once the
                waveform completes (default True)
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
                color=HSBK.from_rgb(1.0, 0.0, 0.0),
                period=1.0,
                cycles=5,
                waveform=LightWaveform.PULSE,
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
        if period < 0:
            raise ValueError(f"Period must be non-negative, got {period}")
        if cycles <= 0:
            raise ValueError(f"Cycles must be greater than 0, got {cycles}")
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
        self._zones_changed()
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
        """Apply a waveform with selective color component control.

        Similar to set_waveform() but allows fine-grained control over which
        color components (hue, saturation, brightness, kelvin) are affected
        by the waveform. This enables pulsing brightness while keeping hue
        constant, or cycling hue while maintaining brightness.

        Cycles may be fractional; 0.5 is a half cycle. On a colour bulb, a
        half cycle moves towards the target for half a period, then a
        transient waveform jumps straight back to the original colour
        (no fade back), while a non-transient one stays at the target.

        Args:
            color: Target color for the waveform
            period: Period of one cycle in seconds. Zero requests an immediate
                transition.
            cycles: Number of cycles, must be greater than 0 (may be fractional)
            waveform: Waveform type (SAW, SINE, HALF_SINE, TRIANGLE, PULSE)
            transient: If True, return to the original color once the
                waveform completes (default True)
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
                cycles=1000,
                waveform=LightWaveform.SAW,
                set_hue=True,
                set_saturation=False,
                set_brightness=False,
                set_kelvin=False,
            )
            ```
        """
        if period < 0:
            raise ValueError(f"Period must be non-negative, got {period}")
        if cycles <= 0:
            raise ValueError(f"Cycles must be greater than 0, got {cycles}")
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
        self._zones_changed()
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

        Convenience method using the PULSE waveform.

        Args:
            color: Target color to pulse to
            period: Period of one pulse in seconds (default 1.0)
            cycles: Number of pulses (default 1)
            transient: If True, return to the original color once the
                waveform completes (default True)

        Example:
            ```python
            # Pulse red once
            await light.pulse(HSBK.from_rgb(1.0, 0.0, 0.0))

            # Pulse blue 3 times, 2 seconds per pulse
            await light.pulse(HSBK.from_rgb(0.0, 0.0, 1.0), period=2.0, cycles=3)
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

        Convenience method using the SINE waveform.

        Args:
            color: Target color to breathe to
            period: Period of one breath in seconds (default 2.0)
            cycles: Number of breaths (default 1)

        Example:
            ```python
            # Breathe white once
            await light.breathe(HSBK(0, 0, 1.0, 3500))

            # Breathe purple 10 times
            await light.breathe(HSBK.from_rgb(0.5, 0.0, 0.5), cycles=10)
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

    async def _fetch_ambient_light_level(self) -> float | None:
        """Query the ambient light sensor when enabled, else return None.

        Every product answers packet 401, whether or not it has a sensor: one
        without reports 0.0, which is also what a device in complete darkness
        reports and what a device that cannot read its sensor reports. There is
        no way to tell those three apart from the response, so this returns the
        reading as-is. The None result is reserved for the query not running -
        the flag is off, or the request failed outright, which leaves the field
        None rather than failing every state fetch it takes part in.

        Returns:
            Ambient light level in lux, or None when the sensor is not queried
            or the request failed
        """
        if not self._fetch_ambient_light:
            return None

        return await self._fetch_optional(
            "ambient_light", self.get_ambient_light_level()
        )

    @staticmethod
    def _ambient_light_reading(lux: float | None, power: int) -> float | None:
        """Mark a reading taken while the light was on as invalid.

        The sensor sits behind the light's own LEDs, so a reading taken while
        the light is on measures the light rather than the room. State fetches
        happen whenever the library refreshes - including the debounced refresh
        that follows ``set_power()`` and ``set_color()`` - so those readings are
        stored as :data:`INVALID_AMBIENT_LIGHT_RESPONSE`, a level the sensor cannot
        report, rather than as a plausible-looking lux value.

        Args:
            lux: Reading from the sensor, or None when it was not queried
            power: Power level the same state fetch read from the device

        Returns:
            The reading, :data:`INVALID_AMBIENT_LIGHT_RESPONSE` if the light was on, or
            None when the sensor was not queried
        """
        if lux is None:
            return None

        return INVALID_AMBIENT_LIGHT_RESPONSE if power > 0 else lux

    async def refresh_state(self) -> None:
        """Refresh light state from hardware.

        Fetches color (which includes power and label), plus the WiFi signal
        and ambient light reading when :attr:`fetch_wifi_info` and
        :attr:`fetch_ambient_light` are set, and updates state. Initializes
        state first when the device has none yet.

        Raises:
            LifxTimeoutError: If device does not respond
            LifxDeviceNotFoundError: If device cannot be reached
        """
        if self._state is None:
            await self._initialize_state()
            return

        # GetColor returns color, power, and label in one request. The optional
        # queries join the same batch when enabled.
        pending: list[asyncio.Future[Any]] = []
        color_task = self._schedule_request(self.get_color(), pending)
        wifi_signal_task = self._schedule_request(self._fetch_wifi_signal(), pending)
        thread_info_task = self._schedule_request(self._fetch_thread_reading(), pending)
        ambient_light_task = self._schedule_request(
            self._fetch_ambient_light_level(), pending
        )

        try:
            await self._await_batch(pending)
        except BaseException:
            await self._discard_pending(pending)
            raise

        color, power, label = color_task.result()
        self._state.color = color
        self._state.power = power
        self._state.label = label

        # Both are assigned unconditionally: with the query disabled the value
        # is None, so the field reports "not fetched" instead of carrying an
        # unbounded-age reading behind a freshly stamped last_updated. The flags
        # are read once, by the queries themselves, so a concurrent toggle
        # cannot blank a reading the device did return.
        self._state.wifi_info = WifiInfo(
            signal=wifi_signal_task.result(), host_firmware=self._state.host_firmware
        )
        self._state.thread_info = thread_info_task.result()
        self._state.ambient_light = self._ambient_light_reading(
            ambient_light_task.result(), power
        )

        self._state.last_updated = time.time()

    async def _initialize_state(self) -> LightState:
        """Initialize light state transactionally.

        Extends base implementation to fetch color in addition to base state.
        When capabilities are not pre-loaded, get_version() runs in parallel with
        the other GET requests to save one network round-trip.

        Raises:
            LifxTimeoutError: If device does not respond within timeout
            LifxDeviceNotFoundError: If device cannot be reached
            LifxProtocolError: If responses are invalid
        """
        try:
            # The colour and ambient light requests join the batch the base
            # class schedules, so they cost no extra round-trip. GetColor
            # returns colour, power and label together, replacing the separate
            # label and power requests the base state fetch makes.
            pending: list[asyncio.Future[Any]] = []
            requests = self._schedule_common_requests(pending)
            color_task = self._schedule_request(self.get_color(), pending)
            ambient_light_task = self._schedule_request(
                self._fetch_ambient_light_level(), pending
            )

            common = await self._resolve_common_requests(requests, pending)
            color, power, label = color_task.result()

            # Create state instance with color
            self._state = LightState(
                model=common.model,
                label=label,
                serial=self.serial,
                mac_address=common.mac_address,
                capabilities=common.capabilities,
                power=power,
                host_firmware=common.host_firmware,
                wifi_firmware=common.wifi_firmware,
                wifi_info=common.wifi_info,
                thread_info=common.thread_info,
                location=common.location,
                group=common.group,
                color=color,
                ambient_light=self._ambient_light_reading(
                    ambient_light_task.result(), power
                ),
                last_updated=time.time(),
            )

            return self._state

        except LifxTimeoutError as e:
            raise LifxTimeoutError(f"Error initializing state for {self.serial}") from e
        except LifxError as e:
            raise LifxError(f"Error initializing state for {self.serial}") from e


#: How long to wait for a light to report that a power-off has taken effect.
POWER_OFF_WAIT_SECONDS = 2.0

#: How often to ask while waiting for a power-off to take effect.
POWER_OFF_POLL_SECONDS = 0.05


async def wait_until_off(
    light: Light,
    timeout: float = POWER_OFF_WAIT_SECONDS,
    interval: float = POWER_OFF_POLL_SECONDS,
) -> bool:
    """Wait until a light itself reports that it is off.

    Firmware acknowledges a power-off straight away but keeps reporting power
    on, and keeps lighting the old picture, for a few hundred milliseconds
    until the power-off has taken effect. A colour written in that window
    shows as a flash, so callers that turn a light off and then change its
    colours wait here first.

    Args:
        light: The light to ask
        timeout: Seconds to wait before giving up
        interval: Seconds between requests

    Returns:
        True once the light reports off, False if it still reports on when
        ``timeout`` runs out
    """
    deadline = time.monotonic() + timeout
    while await light.get_power() != 0:
        if time.monotonic() >= deadline:
            return False
        await asyncio.sleep(interval)
    return True
