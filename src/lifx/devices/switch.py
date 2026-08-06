"""Switch device class for LIFX Switch and Dimmer devices."""

#  Copyright (c) 2026 Avi Miller <me@dje.li>
#  Licensed under the Universal Permissive License v 1.0 as shown at https://opensource.org/license/UPL

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

from lifx.color import HSBK
from lifx.const import DEFAULT_MAX_RETRIES, DEFAULT_REQUEST_TIMEOUT, LIFX_UDP_PORT
from lifx.devices.base import Device, DeviceState
from lifx.exceptions import LifxError, LifxTimeoutError
from lifx.protocol import packets

_LOGGER = logging.getLogger(__name__)

#: Maximum haptic feedback duration accepted by SetButtonConfig (910).
MAX_HAPTIC_DURATION_MS = 500


@dataclass
class ButtonConfig:
    """Device-wide button configuration for LIFX Switch and Dimmer devices.

    The device stores a single configuration that applies to every button
    backlight on the device - individual backlights cannot be configured
    with different colors.

    Attributes:
        haptic_duration_ms: Duration of haptic feedback after a button press
            in milliseconds (0-500). A value of 0 disables haptic feedback.
            Devices without haptic feedback (such as the LIFX Dimmer) ignore
            this value.
        backlight_on_color: Color and brightness of the button backlight when
            the button is on.
        backlight_off_color: Color and brightness of the button backlight when
            the button is off.
    """

    haptic_duration_ms: int
    backlight_on_color: HSBK
    backlight_off_color: HSBK

    @property
    def as_dict(self) -> dict[str, int | dict[str, float | int]]:
        """Return ButtonConfig as a dict.

        HSBK is not a dataclass, so both backlight colors are expanded via
        :attr:`HSBK.as_dict` to keep the result serialisable.
        """
        return {
            "haptic_duration_ms": self.haptic_duration_ms,
            "backlight_on_color": self.backlight_on_color.as_dict,
            "backlight_off_color": self.backlight_off_color.as_dict,
        }


@dataclass
class SwitchState(DeviceState):
    """Switch device state with button configuration.

    Attributes:
        button_config: Device-wide button backlight and haptic configuration,
            or None when the device did not answer the button-config query
            (e.g. firmware without packet 909 support). State initialization
            and refresh tolerate that instead of failing outright.
    """

    button_config: ButtonConfig | None

    @property
    def as_dict(self) -> Any:
        """Return SwitchState as a dict."""
        state: dict[str, Any] = super().as_dict
        state["button_config"] = (
            self.button_config.as_dict if self.button_config is not None else None
        )
        return state


class Switch(Device[SwitchState]):
    """LIFX Switch or Dimmer device with button configuration control.

    Switches and dimmers are "non-light" devices: they respond to device
    messages (label, power, version, location, group) like any other LIFX
    device, but answer light messages with StateUnhandled. This class
    extends the base Device with control over the device-wide button
    configuration: the haptic feedback duration and the backlight colors
    used when a button is `on` and `off`.

    Example:
        ```python
        switch = Switch(serial="d073d5123456", ip="192.168.1.100")

        async with switch:
            # Read the current button configuration
            config = await switch.get_button_config()
            print(f"Haptic duration: {config.haptic_duration_ms}ms")

            # Set the backlight colors, keeping the haptic duration
            await switch.set_button_config(
                backlight_on_color=HSBK(
                    hue=120, saturation=1.0, brightness=0.8, kelvin=3500
                ),
                backlight_off_color=HSBK(
                    hue=0, saturation=0.0, brightness=0.1, kelvin=3500
                ),
            )
        ```

        Using the simplified connect method:
        ```python
        async with await Device.connect(ip="192.168.1.100") as switch:
            assert isinstance(switch, Switch)
            await switch.set_button_config(haptic_duration_ms=0)
        ```
    """

    def __init__(
        self,
        serial: str,
        ip: str,
        port: int = LIFX_UDP_PORT,
        timeout: float = DEFAULT_REQUEST_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        *,
        fetch_wifi_info: bool = False,
        fetch_ambient_light: bool = False,
    ) -> None:
        """Initialize Switch with additional state attributes.

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
            fetch_ambient_light=fetch_ambient_light,
        )
        # Switch-specific state storage
        self._button_config: ButtonConfig | None = None

    @property
    def state(self) -> SwitchState:
        """Get switch state (guaranteed when using Device.connect()).

        Returns:
            SwitchState with current switch state

        Raises:
            RuntimeError: If accessed before state initialization
        """
        if self._state is None:
            raise RuntimeError("State not found.")
        return self._state

    async def _setup(self) -> None:
        """Populate switch capabilities, state and metadata."""
        await super()._setup()
        await self._fetch_button_config()

    async def _fetch_button_config(self) -> ButtonConfig | None:
        """Fetch the button configuration, returning None if the device refuses.

        The button configuration is additive state: a switch whose firmware
        does not answer GetButtonConfig (909) must still initialize and
        refresh its device-level state, leaving the field None rather than
        failing the whole batch. Direct callers use :meth:`get_button_config`,
        which raises instead.

        Returns:
            The configuration, or None when the device did not supply one
        """
        try:
            return await self.get_button_config()
        except LifxError as e:
            _LOGGER.warning(
                {
                    "class": "Switch",
                    "method": "_fetch_button_config",
                    "action": "optional_query_failed",
                    "query": "button_config",
                    "serial": self.serial,
                    "error": str(e),
                }
            )
            return None

    async def get_button_config(self) -> ButtonConfig:
        """Get the device-wide button configuration.

        Always fetches from device. Use the `button_config` property to access
        the stored value.

        Returns:
            ButtonConfig with haptic duration and backlight on/off colors

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxProtocolError: If response is invalid
            LifxUnsupportedCommandError: If device doesn't support this command

        Example:
            ```python
            config = await switch.get_button_config()
            print(f"Haptic duration: {config.haptic_duration_ms}ms")
            print(f"Backlight on: {config.backlight_on_color}")
            print(f"Backlight off: {config.backlight_off_color}")
            ```
        """
        state = await self.connection.request(packets.Button.GetConfig())
        self._raise_if_unhandled(state)

        config = ButtonConfig(
            haptic_duration_ms=state.haptic_duration_ms,
            backlight_on_color=HSBK.from_protocol(state.backlight_on_color),
            backlight_off_color=HSBK.from_protocol(state.backlight_off_color),
        )

        # Store cached state
        self._button_config = config

        # Update state if it exists
        if self._state is not None and hasattr(self._state, "button_config"):
            self._state.button_config = config
            self._state.last_updated = time.time()

        _LOGGER.debug(
            {
                "class": "Switch",
                "method": "get_button_config",
                "action": "query",
                "reply": config.as_dict,
            },
        )

        return config

    async def set_button_config(
        self,
        *,
        haptic_duration_ms: int | None = None,
        backlight_on_color: HSBK | None = None,
        backlight_off_color: HSBK | None = None,
    ) -> None:
        """Set the device-wide button configuration.

        The device stores a single configuration covering the haptic feedback
        duration and both backlight colors, and SetButtonConfig always writes
        all three fields. Any argument left as None keeps its current value,
        read from the cached configuration or fetched from the device first.

        The configuration applies to the whole device - individual backlights
        cannot be configured with different colors. The LIFX Dimmer has no
        haptic feedback and ignores ``haptic_duration_ms``.

        Args:
            haptic_duration_ms: Haptic feedback duration in milliseconds
                (0-500). 0 disables haptic feedback.
            backlight_on_color: Backlight color and brightness when the
                button is on.
            backlight_off_color: Backlight color and brightness when the
                button is off.

        Raises:
            ValueError: If haptic_duration_ms is outside 0-500
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxUnsupportedCommandError: If device doesn't support this command

        Example:
            ```python
            # Green when on, dim white when off, no haptic feedback
            await switch.set_button_config(
                haptic_duration_ms=0,
                backlight_on_color=HSBK(
                    hue=120, saturation=1.0, brightness=0.8, kelvin=3500
                ),
                backlight_off_color=HSBK(
                    hue=0, saturation=0.0, brightness=0.1, kelvin=3500
                ),
            )

            # Change only the "on" color, keeping everything else
            await switch.set_button_config(
                backlight_on_color=HSBK(
                    hue=200, saturation=1.0, brightness=0.5, kelvin=3500
                ),
            )
            ```
        """
        if haptic_duration_ms is not None and not (
            0 <= haptic_duration_ms <= MAX_HAPTIC_DURATION_MS
        ):
            raise ValueError(
                f"Haptic duration must be 0-{MAX_HAPTIC_DURATION_MS}ms, "
                f"got {haptic_duration_ms}"
            )

        # SetButtonConfig writes the whole configuration, so unspecified
        # fields are filled in from the current one (read-modify-write).
        if (
            haptic_duration_ms is None
            or backlight_on_color is None
            or backlight_off_color is None
        ):
            current = self._button_config
            if current is None:
                current = await self.get_button_config()
            if haptic_duration_ms is None:
                haptic_duration_ms = current.haptic_duration_ms
            if backlight_on_color is None:
                backlight_on_color = current.backlight_on_color
            if backlight_off_color is None:
                backlight_off_color = current.backlight_off_color

        # Request automatically handles acknowledgement
        result = await self.connection.request(
            packets.Button.SetConfig(
                haptic_duration_ms=haptic_duration_ms,
                backlight_on_color=backlight_on_color.to_protocol(),
                backlight_off_color=backlight_off_color.to_protocol(),
            ),
        )
        self._raise_if_unhandled(result)

        _LOGGER.debug(
            {
                "class": "Switch",
                "method": "set_button_config",
                "action": "change",
                "values": {
                    "haptic_duration_ms": haptic_duration_ms,
                    "backlight_on_color": backlight_on_color.as_dict,
                    "backlight_off_color": backlight_off_color.as_dict,
                },
            },
        )

        # Update cache and state on acknowledgement
        if result:
            config = ButtonConfig(
                haptic_duration_ms=haptic_duration_ms,
                backlight_on_color=backlight_on_color,
                backlight_off_color=backlight_off_color,
            )
            self._button_config = config
            if self._state is not None:
                self._state.button_config = config

        # Schedule refresh to validate state
        if self._state is not None:
            await self._schedule_refresh()

    @property
    def button_config(self) -> ButtonConfig | None:
        """Get cached button configuration if available.

        Returns:
            Config or None if never fetched.
            Use get_button_config() to fetch from device.
        """
        return self._button_config

    async def refresh_state(self) -> None:
        """Refresh switch state from hardware.

        Fetches label, power and the button configuration.

        Raises:
            LifxTimeoutError: If device does not respond
            LifxDeviceNotFoundError: If device cannot be reached
        """
        await super().refresh_state()

        self.state.button_config = await self._fetch_button_config()

    async def _initialize_state(self) -> SwitchState:
        """Initialize switch state transactionally.

        Extends the base implementation to fetch the button configuration in
        the same parallel batch as the common state requests, so it costs no
        extra round-trip.

        Raises:
            LifxTimeoutError: If device does not respond within timeout
            LifxDeviceNotFoundError: If device cannot be reached
            LifxProtocolError: If responses are invalid
        """
        try:
            pending: list[asyncio.Future[Any]] = []
            requests = self._schedule_common_requests(pending)
            label_task = self._schedule_request(self.get_label(), pending)
            power_task = self._schedule_request(self.get_power(), pending)
            button_config_task = self._schedule_request(
                self._fetch_button_config(), pending
            )

            common = await self._resolve_common_requests(requests, pending)

            # Create state instance with button configuration
            self._state = SwitchState(
                model=common.model,
                label=label_task.result(),
                serial=self.serial,
                mac_address=common.mac_address,
                capabilities=common.capabilities,
                power=power_task.result(),
                host_firmware=common.host_firmware,
                wifi_firmware=common.wifi_firmware,
                wifi_info=common.wifi_info,
                location=common.location,
                group=common.group,
                button_config=button_config_task.result(),
                last_updated=time.time(),
            )

            return self._state

        except LifxTimeoutError as e:
            raise LifxTimeoutError(f"Error initializing state for {self.serial}") from e
        except LifxError as e:
            raise LifxError(f"Error initializing state for {self.serial}") from e
