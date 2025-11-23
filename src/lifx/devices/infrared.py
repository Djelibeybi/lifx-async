"""Infrared light device class for LIFX lights with IR capability."""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass
from typing import Any

from lifx.devices.light import Light, LightState
from lifx.protocol import packets

_LOGGER = logging.getLogger(__name__)


@dataclass
class InfraredLightState(LightState):
    """Infrared light device state with IR control.

    Attributes:
        infrared: Infrared brightness (0.0-1.0)
    """

    infrared: float

    @property
    def as_dict(self) -> Any:
        """Return InfraredLightState as dict."""
        return asdict(self)

    @classmethod
    def from_light_state(
        cls, light_state: LightState, infrared: float
    ) -> InfraredLightState:
        """Create InfraredLightState from LightState."""
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
            infrared=infrared,
            last_updated=time.time(),
        )


class InfraredLight(Light):
    """LIFX infrared light with IR LED control.

    Extends the Light class with infrared brightness control. Infrared LEDs
    automatically activate in low-light conditions to provide illumination for
    night vision cameras.

    Example:
        ```python
        light = InfraredLight(serial="d073d5123456", ip="192.168.1.100")

        async with light:
            # Set infrared brightness to 50%
            await light.set_infrared(0.5)

            # Get current infrared brightness
            brightness = await light.get_infrared()
            print(f"IR brightness: {brightness * 100}%")
        ```

        Using the simplified connect method:
        ```python
        async with await InfraredLight.from_ip(ip="192.168.1.100") as light:
            await light.set_infrared(0.8)
        ```
    """

    _state: InfraredLightState

    def __init__(self, *args, **kwargs) -> None:
        """Initialize InfraredLight with additional state attributes."""
        super().__init__(*args, **kwargs)
        # Infrared-specific state storage
        self._infrared: float | None = None

    @property
    def state(self) -> InfraredLightState:
        """Get infrared light state (guaranteed when using Device.connect()).

        Returns:
            InfraredLightState with current infrared light state

        Raises:
            RuntimeError: If accessed before state initialization
        """
        if self._state is None:
            raise RuntimeError("State not found.")
        return self._state

    async def _setup(self) -> None:
        """Populate Infrared light capabilities, state and metadata."""
        await super()._setup()
        await self.get_infrared()

    async def get_infrared(self) -> float:
        """Get current infrared brightness.

        Returns:
            Infrared brightness (0.0-1.0)

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxProtocolError: If response is invalid
            LifxUnsupportedCommandError: If device doesn't support this command

        Example:
            ```python
            brightness = await light.get_infrared()
            if brightness > 0:
                print(f"IR LEDs active at {brightness * 100}%")
            ```
        """
        # Request infrared state
        state = await self.connection.request(packets.Light.GetInfrared())
        self._raise_if_unhandled(state)

        # Convert from uint16 (0-65535) to float (0.0-1.0)
        brightness = state.brightness / 65535.0

        # Store cached state
        self._infrared = brightness

        # Update state if it exists
        if self._state is not None and hasattr(self._state, "infrared"):
            self._state.infrared = brightness
            self._state.last_updated = __import__("time").time()

        # Update state if it exists
        if self._state is not None and hasattr(self._state, "infrared"):
            self._state.infrared = brightness
            self._state.last_updated = __import__("time").time()

        _LOGGER.debug(
            {
                "class": "Device",
                "method": "get_infrared",
                "action": "query",
                "reply": {"brightness": state.brightness},
            }
        )

        return brightness

    async def set_infrared(self, brightness: float) -> None:
        """Set infrared brightness.

        Args:
            brightness: Infrared brightness (0.0-1.0)

        Raises:
            ValueError: If brightness is out of range
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxUnsupportedCommandError: If device doesn't support this command

        Example:
            ```python
            # Set to 75% infrared brightness
            await light.set_infrared(0.75)

            # Turn off infrared
            await light.set_infrared(0.0)
            ```
        """
        if not (0.0 <= brightness <= 1.0):
            raise ValueError(
                f"Brightness must be between 0.0 and 1.0, got {brightness}"
            )

        # Convert from float (0.0-1.0) to uint16 (0-65535)
        brightness_u16 = max(0, min(65535, int(round(brightness * 65535))))

        # Request automatically handles acknowledgement
        result = await self.connection.request(
            packets.Light.SetInfrared(brightness=brightness_u16),
        )
        self._raise_if_unhandled(result)

        _LOGGER.debug(
            {
                "class": "InfraredLight",
                "method": "set_infrared",
                "action": "change",
                "values": {"brightness": brightness_u16},
            }
        )

        # Update cache and state on acknowledgement
        if result:
            self._infrared = brightness
            if self._state is not None:
                self._state.infrared = brightness

        # Schedule refresh to validate state
        if self._state is not None:
            await self._schedule_refresh()

    @property
    def infrared(self) -> float | None:
        """Get cached infrared brightness if available.

        Returns:
            Brightness (0.0-1.0) or None if never fetched.
            Use get_infrared() to fetch from device.
        """
        return self._infrared

    async def refresh_state(self) -> None:
        """Refresh infrared light state from hardware.

        Fetches color and infrared brightness.

        Raises:
            RuntimeError: If state has not been initialized
            LifxTimeoutError: If device does not respond
            LifxDeviceNotFoundError: If device cannot be reached
        """
        await super().refresh_state()

        infrared = await self.get_infrared()
        self._state.infrared = infrared

    async def _initialize_state(self) -> InfraredLightState:
        """Initialize infrared light state transactionally.

        Extends Light implementation to fetch infrared brightness.

        Args:
            timeout: Timeout for state initialization

        Raises:
            LifxTimeoutError: If device does not respond within timeout
            LifxDeviceNotFoundError: If device cannot be reached
            LifxProtocolError: If responses are invalid
        """
        light_state = await super()._initialize_state()
        infrared = await self.get_infrared()

        # Create state instance with infrared field
        self._state: InfraredLightState = InfraredLightState.from_light_state(
            light_state=light_state,
            infrared=infrared,
        )

        return self._state
