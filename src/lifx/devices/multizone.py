"""MultiZone light device class for LIFX strips and beams."""

from __future__ import annotations

import asyncio
import logging
import math
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from lifx.color import HSBK
from lifx.const import DEFAULT_MAX_RETRIES, DEFAULT_REQUEST_TIMEOUT, LIFX_UDP_PORT
from lifx.devices.component_state import derive_effect_palette, validate_effect_palette
from lifx.devices.light import Light, LightState
from lifx.exceptions import LifxProtocolError, LifxTimeoutError
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

# Wire bounds for the typed Move builder's converted speed (uint32
# milliseconds) and duration (uint64 nanoseconds).
_UINT32_MAX = 2**32 - 1
_UINT64_MAX = 2**64 - 1


def _coerce_direction(value: Direction | str) -> Direction:
    """Coerce a Direction member or its case-insensitive name to a Direction.

    Args:
        value: A ``Direction`` member, or a string naming one
            case-insensitively (``"forward"``, ``"reversed"``).

    Returns:
        The matching ``Direction`` member.

    Raises:
        ValueError: If value is not a ``Direction`` member and not a string
            naming one. A bare integer, ``None`` and a ``bool`` are all
            rejected; the message names the accepted names.
    """
    if isinstance(value, Direction):
        return value
    if isinstance(value, str):
        try:
            return Direction[value.upper()]
        except KeyError:
            pass
    raise ValueError(
        "direction must be a Direction member or one of 'forward'/'reversed' "
        f"(case-insensitive), got {value!r}"
    )


@dataclass
class MultiZoneEffect:
    """MultiZone effect configuration.

    Attributes:
        effect_type: Type of effect (OFF, MOVE)
        speed: Effect speed in milliseconds
        duration: Total effect duration (0 for infinite)
        parameters: Effect-specific parameters (8 uint32 values)

    Use :meth:`move` to build a Move effect from a direction and float
    seconds. The raw constructor and its ``parameters`` list are unchanged
    for callers who already encode them directly (for example, Home
    Assistant).
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

    @staticmethod
    def _seconds_to_units(
        value: float, per_second: int, maximum: int, name: str
    ) -> int:
        """Convert a float number of seconds to a bounded integer wire unit.

        Args:
            value: Number of seconds, as an ``int`` or ``float``.
            per_second: Wire units per second (1000 for milliseconds,
                1_000_000_000 for nanoseconds).
            maximum: Maximum permitted wire value, inclusive.
            name: Field name ("speed" or "duration") used in error messages.

        Returns:
            ``round(value * per_second)``, guaranteed to be within
            ``0..maximum``.

        Raises:
            TypeError: If value is a ``bool`` or is not an ``int`` or
                ``float`` instance.
            ValueError: If value is negative, not finite, or the scaled
                value is not finite or exceeds ``maximum``. An ``int`` too
                large for a float, and a finite float whose scaled value
                overflows to infinity, both raise this same overflow
                ``ValueError`` rather than escaping as ``OverflowError``.
        """
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(
                f"{name} must be a number of seconds (int or float), "
                f"got {type(value).__name__}"
            )
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"{name} must be finite, got {value}")
        if value < 0:
            raise ValueError(f"{name} must be non-negative, got {value}")

        overflow_message = (
            f"{name} of {value} seconds converts to more than the wire "
            f"maximum of {maximum}"
        )
        # An int scales exactly with no float conversion, so it is never
        # non-finite here; math.isfinite() is only ever called on a float
        # (an int too large for a float would otherwise raise OverflowError
        # from math.isfinite() itself, escaping the promised ValueError).
        scaled = value * per_second
        if isinstance(scaled, float) and not math.isfinite(scaled):
            raise ValueError(overflow_message)

        result = round(scaled)
        if result > maximum:
            raise ValueError(overflow_message)
        return result

    @classmethod
    def move(
        cls,
        direction: Direction | str,
        speed: float,
        duration: float = 0,
    ) -> MultiZoneEffect:
        """Build a Move effect from a direction and float seconds.

        Args:
            direction: A ``Direction`` member, or its case-insensitive name
                (``"forward"``, ``"reversed"``).
            speed: Number of seconds per full cycle, rounded to the nearest
                whole millisecond.
            duration: Number of seconds the effect runs for; ``0`` (the
                default) means indefinitely. Rounded to the nearest whole
                nanosecond.

        Returns:
            A ``MultiZoneEffect`` with ``effect_type`` set to
            ``FirmwareEffect.MOVE`` and the eight-slot ``parameters`` list
            encoded internally.

        Raises:
            ValueError: If direction is not a ``Direction`` member and not
                one of its names (a bare ``bool`` included, since it is
                neither); or if speed or duration is negative, not finite,
                or converts to a value larger than the wire can hold
                (``uint32`` for speed, ``uint64`` for duration).
            TypeError: If speed or duration is a ``bool`` or is not an
                ``int`` or ``float``.

        Example:
            ```python
            from lifx import Direction, MultiZoneEffect

            effect = MultiZoneEffect.move(Direction.FORWARD, 5.0)
            await light.set_effect(effect)
            ```
        """
        resolved_direction = _coerce_direction(direction)
        speed_ms = cls._seconds_to_units(speed, 1000, _UINT32_MAX, "speed")
        duration_ns = cls._seconds_to_units(
            duration, 1_000_000_000, _UINT64_MAX, "duration"
        )
        return cls(
            effect_type=FirmwareEffect.MOVE,
            speed=speed_ms,
            duration=duration_ns,
            parameters=[0, int(resolved_direction), 0, 0, 0, 0, 0, 0],
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
    def direction(self, value: Direction | str) -> None:
        """Set direction for MOVE effect.

        Args:
            value: A ``Direction`` member, or its case-insensitive name
                (``"forward"``, ``"reversed"``).

        Raises:
            ValueError: If effect type is not MOVE, or if value is not a
                ``Direction`` member and not one of its names. A bare
                integer is rejected; wrap it as ``Direction(value)`` first.
        """
        if self.effect_type != FirmwareEffect.MOVE:
            raise ValueError(
                f"Direction can only be set for MOVE effects, "
                f"current type is {self.effect_type.name}"
            )
        self.parameters = [0, int(_coerce_direction(value)), 0, 0, 0, 0, 0, 0]


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
        state = super().as_dict
        state["zones"] = [zone.as_dict for zone in self.zones]
        state["zone_count"] = self.zone_count
        state["effect"] = self.effect
        return state

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
            wifi_info=light_state.wifi_info,
            thread_info=light_state.thread_info,
            location=light_state.location,
            group=light_state.group,
            color=light_state.color,
            ambient_light=light_state.ambient_light,
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
        from lifx import Direction

        light = MultiZoneLight(serial="d073d5123456", ip="192.168.1.100")

        async with light:
            # Get number of zones
            zone_count = await light.get_zone_count()
            print(f"Device has {zone_count} zones")

            # Set all zones to red
            await light.set_color_zones(
                start=0, end=zone_count - 1, color=HSBK.from_rgb(1.0, 0.0, 0.0)
            )

            # Get colors for first 5 zones
            colors = await light.get_color_zones(0, 4)

            # Apply a moving effect
            await light.set_move_effect(Direction.FORWARD, 5.0)
        ```

        Using the simplified connect method:
        ```python
        from lifx import Direction

        async with await Device.connect(ip="192.168.1.100") as light:
            assert isinstance(light, MultiZoneLight)
            await light.set_move_effect(Direction.FORWARD, 5.0)
        ```
    """

    _state: MultiZoneLightState

    def __init__(
        self,
        serial: str,
        ip: str,
        port: int = LIFX_UDP_PORT,
        timeout: float = DEFAULT_REQUEST_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        *,
        fetch_wifi_info: bool = False,
        fetch_thread_info: bool = False,
        fetch_radio_info: bool = False,
        fetch_ambient_light: bool = False,
    ) -> None:
        """Initialize MultiZoneLight with additional state attributes.

        See :class:`~lifx.devices.base.Device` for parameter documentation. The
        signature is spelled out rather than forwarded as ``*args, **kwargs`` so
        callers get the same type checking the base class offers.
        """
        super().__init__(
            serial,
            ip,
            port,
            timeout,
            max_retries,
            fetch_wifi_info=fetch_wifi_info,
            fetch_thread_info=fetch_thread_info,
            fetch_radio_info=fetch_radio_info,
            fetch_ambient_light=fetch_ambient_light,
        )
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

        Always fetches from the device. Use the ``zone_count`` property to
        access the most recently stored value without a network request.

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
        # The legacy one-zone request is supported by extended multizone devices
        # too and avoids transferring an entire 82-colour extended response when
        # only the count is needed.
        state = await self.connection.request(
            packets.MultiZone.GetColorZones(start_index=0, end_index=0)
        )
        self._raise_if_unhandled(state)

        count = state.count
        self._store_zone_count(count)

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

    def _store_zone_count(self, count: int) -> None:
        """Store a zone count learned from any multizone response."""
        self._zone_count = count
        if self._state is not None:
            self._state.zone_count = count

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

        zone_count = self._zone_count
        if zone_count is not None:
            end = min(zone_count - 1, end)

        colors: list[HSBK] = []
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
                zone_count = state.count
                self._store_zone_count(zone_count)
                end = min(zone_count - 1, end)
                # Extract colors from response (up to 8 colors)
                zones_in_response = min(
                    8,
                    current_end - current_start + 1,
                    max(0, end - current_start + 1),
                )
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
            if start == 0 and zone_count is not None and len(result) == zone_count:
                self._state.zones = result
                self._state.last_updated = time.time()

        if _LOGGER.isEnabledFor(logging.DEBUG):
            debug_colors = [
                {
                    "hue": color.hue,
                    "saturation": color.saturation,
                    "brightness": color.brightness,
                    "kelvin": color.kelvin,
                }
                for color in result
            ]
            _LOGGER.debug(
                {
                    "class": "Device",
                    "method": "get_color_zones",
                    "action": "query",
                    "reply": {
                        "start": start,
                        "end": end,
                        "zone_count": len(result),
                        "colors": debug_colors,
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

        colors: list[HSBK] = []
        zone_count = self._zone_count
        response_received = False

        # The network stack owns both the configured wall-time request budget
        # and the post-response idle timeout for multi-response streams.
        async for packet in self.connection.request_stream(
            packets.MultiZone.GetExtendedColorZones()
        ):
            response_received = True
            self._raise_if_unhandled(packet)
            zone_count = packet.count
            self._store_zone_count(zone_count)
            # Only process valid colors based on colors_count
            for i in range(packet.colors_count):
                if i >= len(packet.colors):
                    break
                protocol_hsbk = packet.colors[i]
                colors.append(HSBK.from_protocol(protocol_hsbk))

            # Early exit if we have all zones
            if len(colors) >= zone_count:
                break

        # DeviceConnection.request_stream() raises LifxTimeoutError before an
        # empty stream can occur. Preserve that contract for custom connection
        # implementations and test doubles instead of inventing a zero-zone
        # device from the absence of a response.
        if not response_received:
            raise LifxTimeoutError(f"No extended color-zone response from {self.ip}")

        # Return only the requested range to caller
        assert zone_count is not None
        end = min(zone_count - 1, end)
        result = colors[start : end + 1]

        # Update state if it exists and we fetched all zones
        if self._state is not None and hasattr(self._state, "zones"):
            if start == 0 and len(result) == zone_count:
                self._state.zones = result
                self._state.last_updated = time.time()

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
            await light.set_color_zones(0, 9, HSBK.from_rgb(1.0, 0.0, 0.0))

            # Set with transition
            await light.set_color_zones(
                0, 9, HSBK.from_rgb(0.0, 1.0, 0.0), duration=2.0
            )

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

        if _LOGGER.isEnabledFor(logging.DEBUG):
            debug_colors = [
                {
                    "hue": color.hue,
                    "saturation": color.saturation,
                    "brightness": color.brightness,
                    "kelvin": color.kelvin,
                }
                for color in colors
            ]
            _LOGGER.debug(
                {
                    "class": "Device",
                    "method": "set_extended_color_zones",
                    "action": "change",
                    "values": {
                        "zone_index": zone_index,
                        "colors_count": len(colors),
                        "colors": debug_colors,
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
            self._state.last_updated = time.time()

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

    async def _derive_move_palette(self) -> list[HSBK] | None:
        """Derive the default Move palette from the strip's own zone colours.

        Reads every zone's colour with ``get_all_color_zones()`` and derives
        a palette with ``derive_effect_palette()``: None when the zones show
        more than one distinct colour (Move then animates what is already
        shown), or a generated three-colour palette when every zone shows one
        colour.

        A timeout or a malformed reply reading the zones is logged at DEBUG
        and Move is still sent, with no palette, rather than turning a
        fire-and-forget effect into a hard failure.

        Returns:
            A derived palette, or None to send no palette.

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxUnsupportedCommandError: If device doesn't support this command
        """
        try:
            zones = await self.get_all_color_zones()
        except (LifxTimeoutError, LifxProtocolError) as err:
            _LOGGER.debug(
                {
                    "class": "MultiZoneLight",
                    "method": "set_move_effect",
                    "action": "palette read failed, sending the effect "
                    "without a palette",
                    "error": type(err).__name__,
                    "values": {"serial": self.serial},
                }
            )
            return None

        return derive_effect_palette(zones, self.min_kelvin, self.max_kelvin)

    async def set_move_effect(
        self,
        direction: Direction | str,
        speed: float,
        duration: float = 0,
        palette: list[HSBK] | None = None,
    ) -> None:
        """Start the firmware Move effect in one call.

        Move rotates the colours already on the strip; it carries no palette
        of its own on the wire. With no palette, the strip's colours are read
        first and left as they are when they differ. When every zone shows
        one colour a three-colour palette is generated (following the LIFX
        app) and passed to :meth:`apply_theme`, which shuffles the palette
        and blends between its colours across the zones, so the strip shows
        a blend of the palette rather than each colour in order. An explicit
        palette is passed to :meth:`apply_theme` unchanged, without first
        reading the strip's colours through :meth:`get_all_color_zones`. The
        raw ``set_effect(MultiZoneEffect)`` path never paints.

        Args:
            direction: A ``Direction`` member, or its case-insensitive name
                (``"forward"``, ``"reversed"``).
            speed: Number of seconds per full cycle.
            duration: Number of seconds the effect runs for; ``0`` (the
                default) means indefinitely.
            palette: Up to 16 colours to paint before Move starts. ``None``
                (the default) derives a palette from the strip's own zones
                as described above.

        Raises:
            ValueError: If direction, speed, duration or an explicit
                palette is invalid.
            TypeError: If speed or duration is a non-numeric value.
            LifxUnsupportedCommandError: If device doesn't support this command
            LifxTimeoutError: If device does not respond
            LifxDeviceNotFoundError: If device is not connected

        Example:
            ```python
            from lifx import Direction

            await light.set_move_effect(Direction.FORWARD, 5.0)
            ```
        """
        effect = MultiZoneEffect.move(direction, speed, duration)

        if palette is not None:
            validate_effect_palette(palette)
            paint = palette
        else:
            paint = await self._derive_move_palette()

        if paint is not None:
            from lifx.theme.theme import Theme

            await self.apply_theme(Theme(list(paint)), duration=0)

        await self.set_effect(effect)

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

    @staticmethod
    def _encode_zone_runs(
        colors: list[HSBK], offset: int = 0
    ) -> list[tuple[int, int, HSBK]]:
        """Collapse a per-zone color list into (start, end, color) runs.

        SetColorZones carries a single color for a range, so a legacy write
        needs one packet per run of identical colors rather than one per zone.
        HSBK equality is defined at uint16 (wire) granularity, so colors that
        serialise identically collapse into the same run.

        Args:
            colors: One color per zone, in zone order
            offset: Zone index that ``colors[0]`` corresponds to

        Returns:
            List of (start_index, end_index, color) tuples, inclusive of both
            indices and offset into device zone numbering
        """
        runs: list[tuple[int, int, HSBK]] = []
        run_start = 0
        for index in range(1, len(colors) + 1):
            if index == len(colors) or colors[index] != colors[run_start]:
                runs.append((run_start + offset, index - 1 + offset, colors[run_start]))
                run_start = index
        return runs

    async def set_all_color_zones(
        self,
        colors: list[HSBK],
        start: int = 0,
        end: int | None = None,
        duration: float = 0.0,
        apply: MultiZoneApplicationRequest = MultiZoneApplicationRequest.APPLY,
    ) -> None:
        """Set zone colors from a full-length color list.

        Automatically chooses between SetExtendedColorZones and SetColorZones
        based on device capabilities, the counterpart to
        :meth:`get_all_color_zones`.

        ``colors`` is indexed by absolute zone number, so ``colors[i]`` is the
        color for zone ``i``. ``start`` and ``end`` select which zones are
        actually written; zones outside that window are never addressed and
        keep whatever they were showing. This makes read-modify-write natural:
        fetch every zone, change the ones you care about, and write back only
        those.

        Extended writes are chunked at 82 colors per packet; legacy writes are
        run-length encoded into ranges, so a flat color costs one packet but a
        gradient costs one packet per zone. Either way every packet but the
        last is sent with NO_APPLY, so the device buffers the whole update and
        applies it in a single step.

        Args:
            colors: One color per zone, indexed by zone number
            start: First zone to write (inclusive, default 0)
            end: Last zone to write (inclusive, defaults to the last color)
            duration: Transition duration in seconds (default 0.0)
            apply: Application mode for the final packet (default APPLY). Pass
                NO_APPLY to buffer this write and apply it with a later call.
                APPLY_ONLY is rejected: it tells the device to discard the
                colors carried by the message and flush only what is already
                buffered, which would silently drop part of this write.

        The window is checked against the zone count only when that count is
        already cached; it is never fetched just to validate. A device that
        went through ``connect()`` or the async context manager always has it,
        so the unchecked case is a hand-constructed light whose first zone
        operation is a write — there the device itself ignores zones it does
        not have.

        Raises:
            ValueError: If colors is empty, the window is invalid or falls
                outside the list, the window exceeds the cached zone count, or
                apply is APPLY_ONLY
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxUnsupportedCommandError: If device doesn't support this command

        Example:
            ```python
            # Recolor zones 10-19, leaving every other zone untouched
            colors = await light.get_all_color_zones()
            colors[10:20] = [HSBK.from_rgb(1.0, 0.0, 0.0)] * 10
            await light.set_all_color_zones(colors, start=10, end=19)

            # Write the whole strip
            await light.set_all_color_zones(colors, duration=2.0)
            ```
        """
        if not colors:
            raise ValueError("Colors list cannot be empty")

        if apply is MultiZoneApplicationRequest.APPLY_ONLY:
            raise ValueError(
                "APPLY_ONLY discards the colors carried by the message, so it "
                "cannot be used to write zones; use APPLY or NO_APPLY"
            )

        if end is None:
            end = len(colors) - 1

        if start < 0 or end < start:
            raise ValueError(f"Invalid zone range: {start}-{end}")

        if end >= len(colors):
            raise ValueError(
                f"Zone range {start}-{end} extends past the {len(colors)}-color list"
            )

        # Deliberately validated against the cached count only: a round trip
        # purely to validate is never warranted, and any device that went
        # through connect() already has the count. See the design spec.
        if self._zone_count is not None and end >= self._zone_count:
            raise ValueError(
                f"Zone range {start}-{end} exceeds the device's "
                f"{self._zone_count} zones"
            )

        if self.capabilities is None:
            await self._ensure_capabilities()

        # Only the window is transmitted. Note the run-length encoding below
        # runs over the window rather than the whole list, so colors just
        # outside it cannot extend a run and spill the write onto zones the
        # caller asked to leave alone.
        window = colors[start : end + 1]

        if self.capabilities and self.capabilities.has_extended_multizone:
            chunks = [window[i : i + 82] for i in range(0, len(window), 82)]
            for chunk_index, chunk in enumerate(chunks):
                is_last = chunk_index == len(chunks) - 1
                await self.set_extended_color_zones(
                    start + chunk_index * 82,
                    chunk,
                    duration=duration,
                    apply=apply if is_last else ExtendedAppReq.NO_APPLY,
                )
            packet_count = len(chunks)
            path = "extended"
        else:
            # SetColorZones indices are uint8, so legacy firmware cannot
            # address beyond zone 255. The bound is on the window, not the
            # list: a longer list with a low window is fine.
            if end > 255:
                raise ValueError(
                    f"Device does not support extended multizone and cannot "
                    f"address zone {end} (limit is 255)"
                )

            runs = self._encode_zone_runs(window, offset=start)
            for run_index, (run_start, run_end, color) in enumerate(runs):
                is_last = run_index == len(runs) - 1
                await self.set_color_zones(
                    run_start,
                    run_end,
                    color,
                    duration=duration,
                    apply=apply if is_last else MultiZoneApplicationRequest.NO_APPLY,
                )
            packet_count = len(runs)
            path = "legacy"

        _LOGGER.debug(
            {
                "class": "MultiZoneLight",
                "method": "set_all_color_zones",
                "action": "change",
                "values": {
                    "start": start,
                    "end": end,
                    "path": path,
                    "packets": packet_count,
                    "duration": duration,
                    "apply": apply.name,
                },
            }
        )

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

        # Write the colors using whichever packet the device supports; this
        # chunks past 82 zones and falls back to SetColorZones on firmware
        # without extended multizone.
        # If light is off and we're turning it on, set colors immediately then fade on
        if power_on and not is_on:
            await self.set_all_color_zones(colors, duration=0)
            await self.set_power(True, duration=duration)
        else:
            # Light is already on, or we're not turning it on - apply with duration
            await self.set_all_color_zones(colors, duration=duration)

    def __repr__(self) -> str:
        """String representation of multizone light."""
        return f"MultiZoneLight(serial={self.serial}, ip={self.ip}, port={self.port})"

    async def refresh_state(self) -> None:
        """Refresh multizone light state from hardware.

        Fetches color, zones, and effect.

        Raises:
            LifxTimeoutError: If device does not respond
            LifxDeviceNotFoundError: If device cannot be reached
        """
        await super().refresh_state()

        zones, effect = await asyncio.gather(
            self.get_all_color_zones(),
            self.get_effect(),
        )

        self._state.zones = zones
        self._state.effect = effect.effect_type

    async def _initialize_state(self) -> MultiZoneLightState:
        """Initialize multizone light state transactionally.

        Extends Light implementation to fetch zones and effect.

        Raises:
            LifxTimeoutError: If device does not respond within timeout
            LifxDeviceNotFoundError: If device cannot be reached
            LifxProtocolError: If responses are invalid
        """
        light_state = await super()._initialize_state()

        zones, effect = await asyncio.gather(
            self.get_all_color_zones(),
            self.get_effect(),
        )

        self._state = MultiZoneLightState.from_light_state(
            light_state=light_state, zones=zones, effect=effect.effect_type
        )

        return self._state
