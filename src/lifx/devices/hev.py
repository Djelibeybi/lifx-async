"""HEV light device class for LIFX lights with anti-bacterial capability."""

from __future__ import annotations

import asyncio
import logging

from lifx.devices.light import Light
from lifx.protocol import packets
from lifx.protocol.models import HevConfig, HevCycleState
from lifx.protocol.protocol_types import LightLastHevCycleResult

_LOGGER = logging.getLogger(__name__)


class HevLight(Light):
    """LIFX HEV light with anti-bacterial cleaning capabilities.

    Extends the Light class with HEV (High Energy Visible) cycle control.
    HEV uses UV-C light to sanitize surfaces and air with anti-bacterial properties.

    Example:
        ```python
        light = HevLight(serial="d073d5123456", ip="192.168.1.100")

        async with light:
            # Start a 2-hour cleaning cycle
            await light.set_hev_cycle(enable=True, duration_seconds=7200)

            # Check cycle status
            state = await light.get_hev_cycle()
            if state.is_running:
                print(f"Cleaning: {state.remaining_s}s remaining")

            # Configure defaults
            await light.set_hev_config(indication=True, duration_seconds=7200)
        ```

        Using the simplified connect method:
        ```python
        async with await HevLight.from_ip(ip="192.168.1.100") as light:
            await light.set_hev_cycle(enable=True, duration_seconds=3600)
        ```
    """

    def __init__(self, *args, **kwargs) -> None:
        """Initialize HevLight with additional state attributes."""
        super().__init__(*args, **kwargs)
        # HEV-specific state storage
        self._hev_config: HevConfig | None = None
        self._hev_result: LightLastHevCycleResult | None = None

    async def _setup(self) -> None:
        """Populate HEV light capabilities, state and metadata."""
        await super()._setup()
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self.get_hev_config())
            tg.create_task(self.get_hev_cycle())
            tg.create_task(self.get_last_hev_result())

    async def get_hev_cycle(self) -> HevCycleState:
        """Get current HEV cycle state.

        Always fetches from device. Use the `hev_cycle` property to access stored value.

        Returns:
            HevCycleState with duration, remaining time, and last power state

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxProtocolError: If response is invalid

        Example:
            ```python
            state = await light.get_hev_cycle()
            if state.is_running:
                print(f"HEV cleaning in progress: {state.remaining_s}s left")
            else:
                print("No active cleaning cycle")
            ```
        """
        # Request HEV cycle state
        state = await self.connection.request(packets.Light.GetHevCycle())

        # Create state object
        cycle_state = HevCycleState(
            duration_s=state.duration_s,
            remaining_s=state.remaining_s,
            last_power=state.last_power,
        )

        _LOGGER.debug(
            {
                "class": "Device",
                "method": "get_hev_cycle",
                "action": "query",
                "reply": {
                    "duration_s": state.duration_s,
                    "remaining_s": state.remaining_s,
                    "last_power": state.last_power,
                },
            }
        )

        return cycle_state

    async def set_hev_cycle(self, enable: bool, duration_seconds: int) -> None:
        """Start or stop a HEV cleaning cycle.

        Args:
            enable: True to start cycle, False to stop
            duration_seconds: Duration of the cleaning cycle in seconds

        Raises:
            ValueError: If duration is negative
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond

        Example:
            ```python
            # Start a 1-hour cleaning cycle
            await light.set_hev_cycle(enable=True, duration_seconds=3600)

            # Stop the current cycle
            await light.set_hev_cycle(enable=False, duration_seconds=0)
            ```
        """
        if duration_seconds < 0:
            raise ValueError(f"Duration must be non-negative, got {duration_seconds}")

        # Request automatically handles acknowledgement
        await self.connection.request(
            packets.Light.SetHevCycle(
                enable=enable,
                duration_s=duration_seconds,
            ),
        )

        _LOGGER.debug(
            {
                "class": "Device",
                "method": "set_hev_cycle",
                "action": "change",
                "values": {"enable": enable, "duration_s": duration_seconds},
            }
        )

    async def get_hev_config(self) -> HevConfig:
        """Get HEV cycle configuration.

        Returns:
            HevConfig with indication and default duration settings

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxProtocolError: If response is invalid

        Example:
            ```python
            config = await light.get_hev_config()
            print(f"Default duration: {config.duration_s}s")
            print(f"Visual indication: {config.indication}")
            ```
        """
        # Request HEV configuration
        state = await self.connection.request(packets.Light.GetHevCycleConfiguration())

        # Create config object
        config = HevConfig(
            indication=state.indication,
            duration_s=state.duration_s,
        )

        # Store cached state
        self._hev_config = config

        _LOGGER.debug(
            {
                "class": "Device",
                "method": "get_hev_config",
                "action": "query",
                "reply": {
                    "indication": state.indication,
                    "duration_s": state.duration_s,
                },
            }
        )

        return config

    async def set_hev_config(self, indication: bool, duration_seconds: int) -> None:
        """Configure HEV cycle defaults.

        Args:
            indication: Whether to show visual indication during cleaning
            duration_seconds: Default duration for cleaning cycles in seconds

        Raises:
            ValueError: If duration is negative
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond

        Example:
            ```python
            # Configure 2-hour default with visual indication
            await light.set_hev_config(indication=True, duration_seconds=7200)
            ```
        """
        if duration_seconds < 0:
            raise ValueError(f"Duration must be non-negative, got {duration_seconds}")

        # Request automatically handles acknowledgement
        await self.connection.request(
            packets.Light.SetHevCycleConfiguration(
                indication=indication,
                duration_s=duration_seconds,
            ),
        )

        # Update cached state
        self._hev_config = HevConfig(indication=indication, duration_s=duration_seconds)
        _LOGGER.debug(
            {
                "class": "Device",
                "method": "set_hev_config",
                "action": "change",
                "values": {"indication": indication, "duration_s": duration_seconds},
            }
        )

    async def get_last_hev_result(
        self,
    ) -> LightLastHevCycleResult:
        """Get result of the last HEV cleaning cycle.

        Returns:
            LightLastHevCycleResult enum value indicating success or interruption reason

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxProtocolError: If response is invalid

        Example:
            ```python
            result = await light.get_last_hev_result()
            if result == LightLastHevCycleResult.SUCCESS:
                print("Last cleaning cycle completed successfully")
            elif result == LightLastHevCycleResult.INTERRUPTED_BY_LAN:
                print("Cycle was interrupted by network command")
            ```
        """
        # Request last HEV result
        state = await self.connection.request(packets.Light.GetLastHevCycleResult())

        # Store cached state
        self._hev_result = state.result

        _LOGGER.debug(
            {
                "class": "Device",
                "method": "get_last_hev_result",
                "action": "query",
                "reply": {"result": state.result.value},
            }
        )

        return state.result

    @property
    def hev_config(self) -> HevConfig | None:
        """Get cached HEV configuration if available.

        Returns:
            Config or None if never fetched.
            Use get_hev_config() to fetch from device.
        """
        return self._hev_config

    @property
    def hev_result(self) -> LightLastHevCycleResult | None:
        """Get cached last HEV cycle result if available.

        Returns:
            Result or None if never fetched.
            Use get_last_hev_result() to fetch from device.
        """
        return self._hev_result
