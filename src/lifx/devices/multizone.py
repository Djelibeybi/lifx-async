"""MultiZone light device class for LIFX strips and beams."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from lifx.color import HSBK
from lifx.devices.light import Light
from lifx.protocol import packets

if TYPE_CHECKING:
    from lifx.theme import Theme
from lifx.protocol.protocol_types import (
    MultiZoneApplicationRequest,
    MultiZoneEffectParameter,
    MultiZoneEffectSettings,
    MultiZoneEffectType,
)
from lifx.protocol.protocol_types import (
    MultiZoneExtendedApplicationRequest as ExtendedAppReq,
)

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

    effect_type: MultiZoneEffectType
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

    def __init__(self, *args, **kwargs) -> None:
        """Initialize MultiZoneLight with additional state attributes."""
        super().__init__(*args, **kwargs)
        # MultiZone-specific state storage
        self._zone_count: tuple[int, float] | None = None
        self._multizone_effect: tuple[MultiZoneEffect | None, float] | None = None
        # Zone colors - list of all zone colors with single timestamp
        # Updated whenever any zone query is performed
        self._zones: tuple[list[HSBK], float] | None = None

    async def _setup(self) -> None:
        """Populate MultiZone light capabilities, state and metadata."""
        await super()._setup()
        await self.get_extended_color_zones(start=0, end=255)

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

        count = state.count

        import time

        self._zone_count = (count, time.time())

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
        start: int,
        end: int,
    ) -> list[HSBK]:
        """Get colors for a range of zones using GetColorZones.

        Always fetches from device.
        Use `zones` property to access stored values.

        Args:
            start: Start zone index (inclusive)
            end: End zone index (inclusive)

        Returns:
            List of HSBK colors, one per zone

        Raises:
            ValueError: If zone indices are invalid
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxProtocolError: If response is invalid

        Example:
            ```python
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
            state = await self.connection.request(
                packets.MultiZone.GetColorZones(
                    start_index=current_start, end_index=current_end
                )
            )

            # Extract colors from response (up to 8 colors)
            zones_in_response = min(8, current_end - current_start + 1)
            for i in range(zones_in_response):
                if i >= len(state.colors):
                    break
                protocol_hsbk = state.colors[i]
                colors.append(HSBK.from_protocol(protocol_hsbk))

            current_start += 8

        result = colors

        # Update zone storage with fetched colors
        import time

        timestamp = time.time()

        # Initialize or get existing zones array
        if self._zones is None:
            zones_array = [HSBK(0, 0, 0, 3500)] * zone_count
        else:
            zones_array, _ = self._zones
            # Ensure array is the right size
            if len(zones_array) != zone_count:
                zones_array = [HSBK(0, 0, 0, 3500)] * zone_count

        # Update the fetched range
        for i, color in enumerate(result):
            zones_array[start + i] = color

        # Store updated zones with new timestamp
        self._zones = (zones_array, timestamp)

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

    async def get_extended_color_zones(self, start: int, end: int) -> list[HSBK]:
        """Get colors for a range of zones using GetExtendedColorZones.

        Always fetches from device.
        Use `zones` property to access stored values.

        Args:
            start: Start zone index (inclusive)
            end: End zone index (inclusive)

        Returns:
            List of HSBK colors, one per zone

        Raises:
            ValueError: If zone indices are invalid
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxProtocolError: If response is invalid

        Example:
            ```python
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

        if self.capabilities and not self.capabilities.has_extended_multizone:
            return await self.get_color_zones(start=start, end=end)

        colors = []

        state = await self.connection.request(
            packets.MultiZone.GetExtendedColorZones(),
            collect_multiple=bool(zone_count > 82),
        )

        # Handle both single packet and list of packets (when collect_multiple=True)
        packets_list = state if isinstance(state, list) else [state]

        for packet in packets_list:
            # Only process valid colors based on colors_count
            for i in range(packet.colors_count):
                if i >= len(packet.colors):
                    break
                protocol_hsbk = packet.colors[i]
                colors.append(HSBK.from_protocol(protocol_hsbk))

        # Update _zones attribute
        import time

        timestamp = time.time()

        # Store all zones directly - device sent complete state
        self._zones = (colors, timestamp)

        # Return only the requested range to caller
        result = colors[start : end + 1]

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
        await self.connection.request(
            packets.MultiZone.SetColorZones(
                start_index=start,
                end_index=end,
                color=protocol_color,
                duration=duration_ms,
                apply=apply,
            ),
        )

        # Update _zones attribute with the values we just set
        import time

        timestamp = time.time()

        # Initialize or get existing zones array
        if self._zones is None:
            # Need zone_count to initialize array
            if self._zone_count is None:
                zone_count = await self.get_zone_count()
            else:
                zone_count, _ = self._zone_count
            zones_array = [HSBK(0, 0, 0, 3500)] * zone_count
        else:
            zones_array, _ = self._zones

        # Update the zones we just set
        for i in range(start, min(end + 1, len(zones_array))):
            zones_array[i] = color

        # Store updated zones with new timestamp
        self._zones = (zones_array, timestamp)

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
    ) -> None:
        """Set colors for multiple zones efficiently (up to 82 zones per call).

        This is more efficient than set_color_zones when setting different colors
        for many zones at once.

        Args:
            zone_index: Starting zone index
            colors: List of HSBK colors to set (max 82)
            duration: Transition duration in seconds (default 0.0)
            apply: Application mode (default APPLY)

        Raises:
            ValueError: If colors list is too long or zone index is invalid
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond

        Example:
            ```python
            # Create a rainbow effect across zones
            colors = [
                HSBK(hue=i * 36, saturation=1.0, brightness=1.0, kelvin=3500)
                for i in range(10)
            ]
            await light.set_extended_color_zones(0, colors)
            ```
        """
        if zone_index < 0:
            raise ValueError(f"Invalid zone index: {zone_index}")
        if len(colors) > 82:
            raise ValueError(f"Too many colors: {len(colors)} (max 82 per request)")
        if len(colors) == 0:
            raise ValueError("Colors list cannot be empty")  # Convert to protocol HSBK
        protocol_colors = [color.to_protocol() for color in colors]

        # Pad to 82 colors if needed
        while len(protocol_colors) < 82:
            protocol_colors.append(HSBK(0, 0, 0, 3500).to_protocol())

        # Convert duration to milliseconds
        duration_ms = int(duration * 1000)

        # Send request
        await self.connection.request(
            packets.MultiZone.SetExtendedColorZones(
                duration=duration_ms,
                apply=apply,
                index=zone_index,
                colors_count=len(colors),
                colors=protocol_colors,
            ),
        )

        # Update _zones attribute with the values we just set
        import time

        timestamp = time.time()

        # Initialize or get existing zones array
        if self._zones is None:
            # Need zone_count to initialize array
            if self._zone_count is None:
                zone_count = await self.get_zone_count()
            else:
                zone_count, _ = self._zone_count
            zones_array = [HSBK(0, 0, 0, 3500)] * zone_count
        else:
            zones_array, _ = self._zones

        # Update the zones we just set
        for i, color in enumerate(colors):
            zone_idx = zone_index + i
            if zone_idx < len(zones_array):
                zones_array[zone_idx] = color

        # Store updated zones with new timestamp
        self._zones = (zones_array, timestamp)

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
                },
            }
        )

    async def get_multizone_effect(self) -> MultiZoneEffect | None:
        """Get current multizone effect.

        Always fetches from device.
        Use the `multizone_effect` property to access stored value.

        Returns:
            MultiZoneEffect if an effect is active, None if no effect

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxProtocolError: If response is invalid

        Example:
            ```python
            effect = await light.get_multizone_effect()
            if effect:
                print(f"Effect: {effect.effect_type}, Speed: {effect.speed}ms")
            ```
        """
        # Request automatically unpacks response
        state = await self.connection.request(packets.MultiZone.GetEffect())

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

        if effect_type == MultiZoneEffectType.OFF:
            result = None
        else:
            result = MultiZoneEffect(
                effect_type=effect_type,
                speed=settings.speed,
                duration=settings.duration,
                parameters=parameters,
            )

        import time

        self._multizone_effect = (result, time.time())

        _LOGGER.debug(
            {
                "class": "Device",
                "method": "get_multizone_effect",
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

    async def set_multizone_effect(
        self,
        effect: MultiZoneEffect,
    ) -> None:
        """Set multizone effect.

        Args:
            effect: MultiZone effect configuration

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond

        Example:
            ```python
            # Apply a move effect
            effect = MultiZoneEffect(
                effect_type=MultiZoneEffectType.MOVE,
                speed=5000,  # 5 seconds per cycle
                duration=0,  # Infinite
            )
            await light.set_multizone_effect(effect)
            ```
        """  # Ensure parameters list is 8 elements
        parameters = effect.parameters or [0] * 8
        if len(parameters) < 8:
            parameters.extend([0] * (8 - len(parameters)))
        parameters = parameters[:8]

        # Send request
        await self.connection.request(
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

        # Update state attribute
        import time

        result = effect if effect.effect_type != MultiZoneEffectType.OFF else None
        self._multizone_effect = (result, time.time())

        _LOGGER.debug(
            {
                "class": "Device",
                "method": "set_multizone_effect",
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
        await self.set_multizone_effect(
            MultiZoneEffect(
                effect_type=MultiZoneEffectType.OFF,
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

    async def set_move_effect(
        self,
        speed: float = 5.0,
        direction: str = "forward",
        duration: float = 0.0,
    ) -> None:
        """Apply a moving effect that shifts colors along the strip.

        Args:
            speed: Speed in seconds per complete cycle (default 5.0)
            direction: "forward" or "backward" (default "forward")
            duration: Total duration in seconds (0 for infinite, default 0.0)

        Raises:
            ValueError: If direction is invalid or speed is non-positive

        Example:
            ```python
            # Move forward at moderate speed
            await light.set_move_effect(speed=5.0, direction="forward")

            # Move backward slowly for 60 seconds
            await light.set_move_effect(speed=10.0, direction="backward", duration=60.0)
            ```
        """
        if speed <= 0:
            raise ValueError(f"Speed must be positive, got {speed}")
        if direction not in ("forward", "backward"):
            raise ValueError(
                f"Direction must be 'forward' or 'backward', got {direction}"
            )

        # Convert speed to milliseconds
        speed_ms = int(speed * 1000)

        # Convert duration to nanoseconds
        duration_ns = int(duration * 1_000_000_000)

        # Set parameter[0] to 1 for backward, 0 for forward
        parameters = [1 if direction == "backward" else 0] + [0] * 7

        await self.set_multizone_effect(
            MultiZoneEffect(
                effect_type=MultiZoneEffectType.MOVE,
                speed=speed_ms,
                duration=duration_ns,
                parameters=parameters,
            )
        )

        _LOGGER.debug(
            {
                "class": "Device",
                "method": "set_move_effect",
                "action": "change",
                "values": {
                    "speed": speed,
                    "direction": direction,
                    "duration": duration,
                },
            }
        )

    # Stored value properties
    @property
    def zone_count(self) -> tuple[int, float] | None:
        """Get stored zone count with timestamp if available.

        Returns:
            Tuple of (zone_count, timestamp) or None if never fetched.
            Use get_zone_count() to fetch from device.
        """
        return self._zone_count

    @property
    def multizone_effect(self) -> tuple[MultiZoneEffect | None, float] | None:
        """Get stored multizone effect with timestamp if available.

        Returns:
            Tuple of (effect, timestamp) or None if never fetched.
            Use get_multizone_effect() to fetch from device.
        """
        return self._multizone_effect

    @property
    def zones(self) -> tuple[list[HSBK], float] | None:
        """Get stored zone colors with timestamp if available.

        Returns:
            Tuple of (zone_colors, timestamp) or None if never fetched.
            Use get_color_zones() or get_extended_color_zones() to fetch from device.
        """
        return self._zones

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
