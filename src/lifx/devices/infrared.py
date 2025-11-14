"""Infrared light device class for LIFX lights with IR capability."""

from __future__ import annotations

import logging

from lifx.devices.light import Light
from lifx.protocol import packets

_LOGGER = logging.getLogger(__name__)


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

    def __init__(self, *args, **kwargs) -> None:
        """Initialize InfraredLight with additional state attributes."""
        super().__init__(*args, **kwargs)
        # Infrared-specific state storage
        self._infrared: float | None = None

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

        Example:
            ```python
            brightness = await light.get_infrared()
            if brightness > 0:
                print(f"IR LEDs active at {brightness * 100}%")
            ```
        """
        # Request infrared state
        state = await self.connection.request(packets.Light.GetInfrared())

        # Convert from uint16 (0-65535) to float (0.0-1.0)
        brightness = state.brightness / 65535.0

        # Store cached state
        self._infrared = brightness

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
        await self.connection.request(
            packets.Light.SetInfrared(brightness=brightness_u16),
        )

        # Update cached state
        self._infrared = brightness
        _LOGGER.debug(
            {
                "class": "Device",
                "method": "set_infrared",
                "action": "change",
                "values": {"brightness": brightness_u16},
            }
        )

    @property
    def infrared(self) -> float | None:
        """Get cached infrared brightness if available.

        Returns:
            Brightness (0.0-1.0) or None if never fetched.
            Use get_infrared() to fetch from device.
        """
        return self._infrared
