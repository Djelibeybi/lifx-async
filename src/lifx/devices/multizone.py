"""MultiZone light device class for LIFX strips and beams."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

from lifx.color import HSBK
from lifx.devices.light import Light, LightState
from lifx.protocol import packets
from lifx.protocol.protocol_types import (
    Direction,
    FirmwareEffect,
    MultiZoneApplicationRequest,
    MultiZoneEffectParameter,
    MultiZoneEffectSettings,
)
from lifx.protocol.protocol_types import (
    MultiZoneApplicationRequest as ExtendedAppReq,
)

if TYPE_CHECKING:
    from lifx.theme import Theme

_LOGGER = logging.getLogger(__name__)


@dataclass
class MultiZoneEffect:
    """MultiZone effect configuration.

    Attributes:
        effect_type: Type of effect (OFF, MOVE)
        speed: Effect speed in milliseconds
        duration: Total effect duration (0 for infinite)
        parameters: Effect-specific parameters (8 uint32 values)
    """

    effect_type: FirmwareEffect
    speed: int
    duration: int = 0
    parameters: list[int] | None = None

    def __post_init__(self) -> None:
        """Initialize defaults and validate fields."""

        if self.parameters is None:
            self.parameters = [0] * 8

        # Validate all fields
        self._validate_speed(self.speed)
        self._validate_duration(self.duration)
        self._validate_parameters(self.parameters)

    @staticmethod
    def _validate_speed(value: int) -> None:
        """Validate effect speed is non-negative.

        Args:
            value: Speed value in milliseconds

        Raises:
            ValueError: If speed is negative
        """
        if value < 0:
            raise ValueError(f"Effect speed must be non-negative, got {value}")

    @staticmethod
    def _validate_duration(value: int) -> None:
        """Validate effect duration is non-negative.

        Args:
            value: Duration value (0 for infinite)

        Raises:
            ValueError: If duration is negative
        """
        if value < 0:
            raise ValueError(f"Effect duration must be non-negative, got {value}")

    @staticmethod
    def _validate_parameters(value: list[int]) -> None:
        """Validate effect parameters list.

        Args:
            value: List of 8 uint32 parameters

        Raises:
            ValueError: If parameters list is invalid
        """
        if len(value) != 8:
            raise ValueError(
                f"Effect parameters must be a list of 8 values, got {len(value)}"
            )
        for i, param in enumerate(value):
            if not (0 <= param < 2**32):
                raise ValueError(
                    f"Parameter {i} must be a uint32 (0-{2**32 - 1}), got {param}"
                )

    @property
    def direction(self) -> Direction | None:
        """Get direction for MOVE effect.

        Returns:
            Direction enum value if effect is MOVE, None otherwise
        """
        if self.effect_type != FirmwareEffect.MOVE:
            return None
        return Direction(self.parameters[1]) if self.parameters else Direction.FORWARD

    @direction.setter
    def direction(self, value: Direction) -> None:
        """Set direction for MOVE effect.

        Args:
            value: Direction enum value

        Raises:
            ValueError: If effect type is not MOVE
        """
        if self.effect_type != FirmwareEffect.MOVE:
            raise ValueError(
                f"Direction can only be set for MOVE effects, "
                f"current type is {self.effect_type.name}"
            )
        self.parameters = [0, int(value), 0, 0, 0, 0, 0, 0, 0]


@dataclass
class MultiZoneLightState(LightState):
    """MultiZone light device state with zone-based control.

    Attributes:
        zones: List of HSBK colors for each zone
        zone_count: Total number of zones
        effect: Current multizone effect configuration
    """

    zones: list[HSBK]
    zone_count: int
    effect: FirmwareEffect

    @property
    def as_dict(self) -> Any:
        """Return MultiZoneLightState as dict."""
        return asdict(self)

    @classmethod
    def from_light_state(
        cls,
        light_state: LightState,
        zones: list[HSBK],
        effect: FirmwareEffect,
    ) -> MultiZoneLightState:
        """Create MatrixLightState from LightState."""
        return cls(
            model=light_state.model,
            label=light_state.label,
            serial=light_state.serial,
            mac_address=light_state.mac_address,
            power=light_state.power,
            capabilities=light_state.capabilities,
            host_firmware=light_state.host_firmware,
            wifi_firmware=light_state.wifi_firmware,
            location=light_state.location,
            group=light_state.group,
            color=light_state.color,
            zones=zones,
            zone_count=len(zones),
            effect=effect,
            last_updated=time.time(),
        )


class MultiZoneLight(Light):
    """LIFX MultiZone light device (strips, beams).

    Extends the Light class with zone-specific functionality:
    - Individual zone color control
    - Multi-zone effects (move, etc.)
    - Extended color zone support for efficient bulk updates

    Example:
        ```python
        light = MultiZoneLight(serial="d073d5123456", ip="192.168.1.100")

        async with light:
            # Get number of zones
            zone_count = await light.get_zone_count()
            print(f"Device has {zone_count} zones")

            # Set all zones to red
            await light.set_color_zones(
                start=0, end=zone_count - 1, color=HSBK.from_rgb(255, 0, 0)
            )

            # Get colors for first 5 zones
            colors = await light.get_color_zones(0, 4)

            # Apply a moving effect
            await light.set_move_effect(speed=5.0, direction="forward")
        ```

        Using the simplified connect method:
        ```python
        async with await MultiZoneLight.from_ip(ip="192.168.1.100") as light:
            await light.set_move_effect(speed=5.0, direction="forward")
        ```
    """

    _state: MultiZoneLightState

    def __init__(self, *args, **kwargs) -> None:
        """Initialize MultiZoneLight with additional state attributes."""
        super().__init__(*args, **kwargs)
        # MultiZone-specific state storage
        self._zone_count: int | None = None
        self._multizone_effect: MultiZoneEffect | None | None = None

    @property
    def state(self) -> MultiZoneLightState:
        """Get multizone light state (guaranteed when using Device.connect()).

        Returns:
            MultiZoneLightState with current multizone light state

        Raises:
            RuntimeError: If accessed before state initialization
        """
        if self._state is None:
            raise RuntimeError("State not found.")
        return self._state

    async def get_zone_count(self) -> int:
        """Get the number of zones in the device.

        Always fetches from device.
        Use the `zone_count` property to access stored value.

        Returns:
            Number of zones

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxProtocolError: If response is invalid
            LifxUnsupportedCommandError: If device doesn't support this command

        Example:
            ```python
            zone_count = await light.get_zone_count()
            print(f"Device has {zone_count} zones")
            ```
        """
        # Request automatically unpacks response
        if self.capabilities and self.capabilities.has_extended_multizone:
            state = await self.connection.request(
                packets.MultiZone.GetExtendedColorZones()
            )
        else:
            state = await self.connection.request(
                packets.MultiZone.GetColorZones(start_index=0, end_index=0)
            )
        self._raise_if_unhandled(state)

        count = state.count

        self._zone_count = count

        _LOGGER.debug(
            {
                "class": "Device",
                "method": "get_zone_count",
                "action": "query",
                "reply": {
                    "count": state.count,
                },
            }
        )

        return count

    async def get_color_zones(
        self,
        start: int = 0,
        end: int = 255,
    ) -> list[HSBK]:
        """Get colors for a range of zones using GetColorZones.

        Always fetches from device.
        Use `zones` property to access stored values.

        Args:
            start: Start zone index (inclusive, default 0)
            end: End zone index (inclusive, default 255)

        Returns:
            List of HSBK colors, one per zone

        Raises:
            ValueError: If zone indices are invalid
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxProtocolError: If response is invalid
            LifxUnsupportedCommandError: If device doesn't support this command

        Example:
            ```python
            # Get colors for all zones (default)
            colors = await light.get_color_zones()

            # Get colors for first 10 zones
            colors = await light.get_color_zones(0, 9)
            for i, color in enumerate(colors):
                print(f"Zone {i}: {color}")
            ```
        """
        if start < 0 or end < start:
            raise ValueError(f"Invalid zone range: {start}-{end}")

        # Ensure capabilities are loaded
        if self.capabilities is None:
            await self._ensure_capabilities()

        zone_count = await self.get_zone_count()
        end = min(zone_count - 1, end)

        colors = []
        current_start = start

        while current_start <= end:
            current_end = min(current_start + 7, end)  # Max 8 zones per request

            # Stream responses - break after first (single response per request)
            async for state in self.connection.request_stream(
                packets.MultiZone.GetColorZones(
                    start_index=current_start, end_index=current_end
                )
            ):
                self._raise_if_unhandled(state)
                # Extract colors from response (up to 8 colors)
                zones_in_response = min(8, current_end - current_start + 1)
                for i in range(zones_in_response):
                    if i >= len(state.colors):
                        break
                    protocol_hsbk = state.colors[i]
                    colors.append(HSBK.from_protocol(protocol_hsbk))
                break  # Single response per request

            current_start += 8

        result = colors

        # Update state if it exists and we fetched all zones
        if self._state is not None and hasattr(self._state, "zones"):
            if start == 0 and len(result) == zone_count:
                self._state.zones = result
                self._state.last_updated = __import__("time").time()

        # Update state if it exists and we fetched all zones
        if self._state is not None and hasattr(self._state, "zones"):
            if start == 0 and len(result) == zone_count:
                self._state.zones = result
                self._state.last_updated = __import__("time").time()

        _LOGGER.debug(
            {
                "class": "Device",
                "method": "get_color_zones",
                "action": "query",
                "reply": {
                    "start": start,
                    "end": end,
                    "zone_count": len(result),
                    "colors": [
                        {
                            "hue": c.hue,
                            "saturation": c.saturation,
                            "brightness": c.brightness,
                            "kelvin": c.kelvin,
                        }
                        for c in result
                    ],
                },
            }
        )

        return result

    async def get_extended_color_zones(
        self, start: int = 0, end: int = 255
    ) -> list[HSBK]:
        """Get colors for a range of zones using GetExtendedColorZones.

        Always fetches from device.
        Use `zones` property to access stored values.

        Args:
            start: Start zone index (inclusive, default 0)
            end: End zone index (inclusive, default 255)

        Returns:
            List of HSBK colors, one per zone

        Raises:
            ValueError: If zone indices are invalid
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxProtocolError: If response is invalid
            LifxUnsupportedCommandError: If device doesn't support this command

        Example:
            ```python
            # Get colors for all zones (default)
            colors = await light.get_extended_color_zones()

            # Get colors for first 10 zones
            colors = await light.get_extended_color_zones(0, 9)
            for i, color in enumerate(colors):
                print(f"Zone {i}: {color}")
            ```
        """
        if start < 0 or end < start:
            raise ValueError(f"Invalid zone range: {start}-{end}")

        zone_count = await self.get_zone_count()
        end = min(zone_count - 1, end)

        colors: list[HSBK] = []

        # Stream all responses until timeout
        async for packet in self.connection.request_stream(
            packets.MultiZone.GetExtendedColorZones(),
            timeout=2.0,  # Allow time for multiple responses
        ):
            self._raise_if_unhandled(packet)
            # Only process valid colors based on colors_count
            for i in range(packet.colors_count):
                if i >= len(packet.colors):
                    break
                protocol_hsbk = packet.colors[i]
                colors.append(HSBK.from_protocol(protocol_hsbk))

            # Early exit if we have all zones
            if len(colors) >= zone_count:
                break

        # Return only the requested range to caller
        result = colors[start : end + 1]

        # Update state if it exists and we fetched all zones
        if self._state is not None and hasattr(self._state, "zones"):
            if start == 0 and len(result) == zone_count:
                self._state.zones = result
                self._state.last_updated = __import__("time").time()

        # Update state if it exists and we fetched all zones
        if self._state is not None and hasattr(self._state, "zones"):
            if start == 0 and len(result) == zone_count:
                self._state.zones = result
                self._state.last_updated = __import__("time").time()

        _LOGGER.debug(
            {
                "class": "Device",
                "method": "get_extended_color_zones",
                "action": "query",
                "reply": {
                    "total_zones": len(colors),
                    "requested_start": start,
                    "requested_end": end,
                    "returned_count": len(result),
                },
            }
        )

        return result

    async def get_all_color_zones(self) -> list[HSBK]:
        """Get colors for all zones, automatically using the best method.

        This method automatically chooses between get_extended_color_zones()
        and get_color_zones() based on device capabilities. Always returns
        all zones on the device.

        Always fetches from device.

        Returns:
            List of HSBK colors for all zones

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxProtocolError: If response is invalid

        Example:
            ```python
            # Get all zones (automatically uses best method)
            colors = await light.get_all_color_zones()
            print(f"Device has {len(colors)} zones")
            ```
        """
        # Ensure capabilities are loaded
        if self.capabilities is None:
            await self._ensure_capabilities()

        # Use extended multizone if available, otherwise fall back to standard
        if self.capabilities and self.capabilities.has_extended_multizone:
            return await self.get_extended_color_zones()
        else:
            return await self.get_color_zones()

    async def set_color_zones(
        self,
        start: int,
        end: int,
        color: HSBK,
        duration: float = 0.0,
        apply: MultiZoneApplicationRequest = MultiZoneApplicationRequest.APPLY,
    ) -> None:
        """Set color for a range of zones.

        Args:
            start: Start zone index (inclusive)
            end: End zone index (inclusive)
            color: HSBK color to set
            duration: Transition duration in seconds (default 0.0)
            apply: Application mode (default APPLY)
                   - NO_APPLY: Don't apply immediately (use for batching)
                   - APPLY: Apply this change and any pending changes
                   - APPLY_ONLY: Apply only this change

        Raises:
            ValueError: If zone indices are invalid
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxUnsupportedCommandError: If device doesn't support this command

        Example:
            ```python
            # Set zones 0-9 to red
            await light.set_color_zones(0, 9, HSBK.from_rgb(255, 0, 0))

            # Set with transition
            await light.set_color_zones(0, 9, HSBK.from_rgb(0, 255, 0), duration=2.0)

            # Batch updates
            await light.set_color_zones(
                0, 4, color1, apply=MultiZoneApplicationRequest.NO_APPLY
            )
            await light.set_color_zones(
                5, 9, color2, apply=MultiZoneApplicationRequest.APPLY
            )
            ```
        """
        if start < 0 or end < start:
            raise ValueError(
                f"Invalid zone range: {start}-{end}"
            )  # Convert to protocol HSBK
        protocol_color = color.to_protocol()

        # Convert duration to milliseconds
        duration_ms = int(duration * 1000)

        # Send request
        result = await self.connection.request(
            packets.MultiZone.SetColorZones(
                start_index=start,
                end_index=end,
                color=protocol_color,
                duration=duration_ms,
                apply=apply,
            ),
        )
        self._raise_if_unhandled(result)

        _LOGGER.debug(
            {
                "class": "Device",
                "method": "set_color_zones",
                "action": "change",
                "values": {
                    "start": start,
                    "end": end,
                    "color": {
                        "hue": color.hue,
                        "saturation": color.saturation,
                        "brightness": color.brightness,
                        "kelvin": color.kelvin,
                    },
                    "duration": duration_ms,
                    "apply": apply.name,
                },
            }
        )

    async def set_extended_color_zones(
        self,
        zone_index: int,
        colors: list[HSBK],
        duration: float = 0.0,
        apply: ExtendedAppReq = ExtendedAppReq.APPLY,
        *,
        fast: bool = False,
    ) -> None:
        """Set colors for multiple zones efficiently (up to 82 zones per call).

        This is more efficient than set_color_zones when setting different colors
        for many zones at once.

        Args:
            zone_index: Starting zone index
            colors: List of HSBK colors to set (max 82)
            duration: Transition duration in seconds (default 0.0)
            apply: Application mode (default APPLY)
            fast: If True, send fire-and-forget without waiting for response.
                  Use for high-frequency animations (>20 updates/second).

        Raises:
            ValueError: If colors list is too long or zone index is invalid
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond (only when fast=False)
            LifxUnsupportedCommandError: If device doesn't support this command
                (only when fast=False)

        Example:
            ```python
            # Create a rainbow effect across zones
            colors = [
                HSBK(hue=i * 36, saturation=1.0, brightness=1.0, kelvin=3500)
                for i in range(10)
            ]
            await light.set_extended_color_zones(0, colors)

            # High-speed animation loop
            for frame in animation_frames:
                await light.set_extended_color_zones(0, frame, fast=True)
                await asyncio.sleep(0.033)  # ~30 FPS
            ```
        """
        if zone_index < 0:
            raise ValueError(f"Invalid zone index: {zone_index}")
        if len(colors) > 82:
            raise ValueError(f"Too many colors: {len(colors)} (max 82 per request)")
        if len(colors) == 0:
            raise ValueError("Colors list cannot be empty")

        # Convert to protocol HSBK
        protocol_colors = [color.to_protocol() for color in colors]

        # Pad to 82 colors if needed
        while len(protocol_colors) < 82:
            protocol_colors.append(HSBK(0, 0, 0, 3500).to_protocol())

        # Convert duration to milliseconds
        duration_ms = int(duration * 1000)

        packet = packets.MultiZone.SetExtendedColorZones(
            duration=duration_ms,
            apply=apply,
            index=zone_index,
            colors_count=len(colors),
            colors=protocol_colors,
        )

        if fast:
            # Fire-and-forget: no ack, no response, no waiting
            await self.connection.send_packet(
                packet,
                ack_required=False,
                res_required=False,
            )
        else:
            # Standard: wait for response and check for errors
            result = await self.connection.request(packet)
            self._raise_if_unhandled(result)

        _LOGGER.debug(
            {
                "class": "Device",
                "method": "set_extended_color_zones",
                "action": "change",
                "values": {
                    "zone_index": zone_index,
                    "colors_count": len(colors),
                    "colors": [
                        {
                            "hue": c.hue,
                            "saturation": c.saturation,
                            "brightness": c.brightness,
                            "kelvin": c.kelvin,
                        }
                        for c in colors
                    ],
                    "duration": duration_ms,
                    "apply": apply.name,
                    "fast": fast,
                },
            }
        )

    async def get_effect(self) -> MultiZoneEffect:
        """Get current multizone effect.

        Always fetches from device.
        Use the `multizone_effect` property to access stored value.

        Returns:
            MultiZoneEffect with either FirmwareEffect.OFF or FirmwareEffect.MOVE

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxProtocolError: If response is invalid
            LifxUnsupportedCommandError: If device doesn't support this command

        Example:
            ```python
            from lifx.protocol.protocol_types import Direction, FirmwareEffect

            effect = await light.get_effect()
            if effect:
                print(f"Effect: {effect.effect_type.name}, Speed: {effect.speed}ms")
                if effect.effect_type == FirmwareEffect.MOVE:
                    print(f"Direction: {effect.direction.name}")
            ```
        """
        # Request automatically unpacks response
        state = await self.connection.request(packets.MultiZone.GetEffect())
        self._raise_if_unhandled(state)

        settings = state.settings
        effect_type = settings.effect_type

        # Extract parameters from the settings parameter field
        parameters = [
            settings.parameter.parameter0,
            settings.parameter.parameter1,
            settings.parameter.parameter2,
            settings.parameter.parameter3,
            settings.parameter.parameter4,
            settings.parameter.parameter5,
            settings.parameter.parameter6,
            settings.parameter.parameter7,
        ]

        result = MultiZoneEffect(
            effect_type=effect_type,
            speed=settings.speed,
            duration=settings.duration,
            parameters=parameters,
        )

        self._multizone_effect = result

        # Update state if it exists
        if self._state is not None and hasattr(self._state, "effect"):
            self._state.effect = result.effect_type
            self._state.last_updated = __import__("time").time()

        _LOGGER.debug(
            {
                "class": "Device",
                "method": "get_effect",
                "action": "query",
                "reply": {
                    "effect_type": effect_type.name,
                    "speed": settings.speed,
                    "duration": settings.duration,
                    "parameters": parameters,
                },
            }
        )

        return result

    async def set_effect(
        self,
        effect: MultiZoneEffect,
    ) -> None:
        """Set multizone effect.

        Args:
            effect: MultiZone effect configuration

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxUnsupportedCommandError: If device doesn't support this command

        Example:
            ```python
            from lifx.protocol.protocol_types import Direction, FirmwareEffect

            # Apply a move effect moving forward
            effect = MultiZoneEffect(
                effect_type=FirmwareEffect.MOVE,
                speed=5000,  # 5 seconds per cycle
                duration=0,  # Infinite
            )
            effect.direction = Direction.FORWARD
            await light.set_effect(effect)

            # Or use parameters directly
            effect = MultiZoneEffect(
                effect_type=FirmwareEffect.MOVE,
                speed=5000,
                parameters=[0, int(Direction.REVERSED), 0, 0, 0, 0, 0, 0],
            )
            await light.set_effect(effect)
            ```
        """  # Ensure parameters list is 8 elements
        parameters = effect.parameters or [0] * 8
        if len(parameters) < 8:
            parameters.extend([0] * (8 - len(parameters)))
        parameters = parameters[:8]

        # Send request
        result = await self.connection.request(
            packets.MultiZone.SetEffect(
                settings=MultiZoneEffectSettings(
                    instanceid=0,  # 0 for new effect
                    effect_type=effect.effect_type,
                    speed=effect.speed,
                    duration=effect.duration,
                    parameter=MultiZoneEffectParameter(
                        parameter0=parameters[0],
                        parameter1=parameters[1],
                        parameter2=parameters[2],
                        parameter3=parameters[3],
                        parameter4=parameters[4],
                        parameter5=parameters[5],
                        parameter6=parameters[6],
                        parameter7=parameters[7],
                    ),
                ),
            ),
        )
        self._raise_if_unhandled(result)

        # Update cached state
        cached_effect = effect if effect.effect_type != FirmwareEffect.OFF else None
        self._multizone_effect = cached_effect

        _LOGGER.debug(
            {
                "class": "Device",
                "method": "set_effect",
                "action": "change",
                "values": {
                    "effect_type": effect.effect_type.name,
                    "speed": effect.speed,
                    "duration": effect.duration,
                    "parameters": parameters,
                },
            }
        )

    async def stop_effect(self) -> None:
        """Stop any running multizone effect.

        Example:
            ```python
            await light.stop_effect()
            ```
        """
        await self.set_effect(
            MultiZoneEffect(
                effect_type=FirmwareEffect.OFF,
                speed=0,
                duration=0,
            )
        )

        _LOGGER.debug(
            {
                "class": "Device",
                "method": "stop_effect",
                "action": "change",
                "values": {},
            }
        )

    # Cached value properties
    @property
    def zone_count(self) -> int | None:
        """Get cached zone count if available.

        Returns:
            Zone count or None if never fetched.
            Use get_zone_count() to fetch from device.
        """
        return self._zone_count

    @property
    def multizone_effect(self) -> MultiZoneEffect | None | None:
        """Get cached multizone effect if available.

        Returns:
            Effect or None if never fetched.
            Use get_effect() to fetch from device.
        """
        return self._multizone_effect

    async def apply_theme(
        self,
        theme: Theme,
        power_on: bool = False,
        duration: float = 0,
        strategy: str | None = None,
    ) -> None:
        """Apply a theme across zones.

        Distributes theme colors evenly across the light's zones with smooth
        color blending between theme colors.

        Args:
            theme: Theme to apply
            power_on: Turn on the light
            duration: Transition duration in seconds
            strategy: Color distribution strategy (not used yet, for future)

        Example:
            ```python
            from lifx.theme import get_theme

            theme = get_theme("evening")
            await strip.apply_theme(theme, power_on=True, duration=0.5)
            ```
        """
        from lifx.theme.generators import MultiZoneGenerator

        # Get number of zones
        zone_count = await self.get_zone_count()

        # Use proper multizone generator with blending
        generator = MultiZoneGenerator()
        colors = generator.get_theme_colors(theme, zone_count)

        # Check if light is on
        is_on = await self.get_power()

        # Apply colors to zones using extended format for efficiency
        # If light is off and we're turning it on, set colors immediately then fade on
        if power_on and not is_on:
            await self.set_extended_color_zones(0, colors, duration=0)
            await self.set_power(True, duration=duration)
        else:
            # Light is already on, or we're not turning it on - apply with duration
            await self.set_extended_color_zones(0, colors, duration=duration)

    def __repr__(self) -> str:
        """String representation of multizone light."""
        return f"MultiZoneLight(serial={self.serial}, ip={self.ip}, port={self.port})"

    async def refresh_state(self) -> None:
        """Refresh multizone light state from hardware.

        Fetches color, zones, and effect.

        Raises:
            RuntimeError: If state has not been initialized
            LifxTimeoutError: If device does not respond
            LifxDeviceNotFoundError: If device cannot be reached
        """
        await super().refresh_state()

        async with asyncio.TaskGroup() as tg:
            zones_task = tg.create_task(self.get_all_color_zones())
            effect_task = tg.create_task(self.get_effect())

        zones = zones_task.result()
        effect = effect_task.result()

        self._state.zones = zones
        self._state.effect = effect.effect_type

    async def _initialize_state(self) -> MultiZoneLightState:
        """Initialize multizone light state transactionally.

        Extends Light implementation to fetch zones and effect.

        Args:
            timeout: Timeout for state initialization

        Raises:
            LifxTimeoutError: If device does not respond within timeout
            LifxDeviceNotFoundError: If device cannot be reached
            LifxProtocolError: If responses are invalid
        """
        light_state = await super()._initialize_state()

        async with asyncio.TaskGroup() as tg:
            zones_task = tg.create_task(self.get_all_color_zones())
            effect_task = tg.create_task(self.get_effect())

        zones = zones_task.result()
        effect = effect_task.result()

        self._state = MultiZoneLightState.from_light_state(
            light_state=light_state, zones=zones, effect=effect.effect_type
        )

        return self._state
