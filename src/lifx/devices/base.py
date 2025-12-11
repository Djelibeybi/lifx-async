"""Base device class for LIFX devices."""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import time
import uuid
from dataclasses import dataclass, field
from math import floor, log10
from typing import TYPE_CHECKING, Generic, Self, TypeVar, cast

from lifx.const import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_REQUEST_TIMEOUT,
    DISCOVERY_TIMEOUT,
    LIFX_GROUP_NAMESPACE,
    LIFX_LOCATION_NAMESPACE,
    LIFX_UDP_PORT,
)
from lifx.exceptions import LifxDeviceNotFoundError, LifxUnsupportedCommandError
from lifx.network.connection import DeviceConnection
from lifx.products.registry import ProductInfo, get_product
from lifx.protocol import packets
from lifx.protocol.models import Serial

if TYPE_CHECKING:
    from lifx.devices import (
        CeilingLight,
        HevLight,
        InfraredLight,
        Light,
        MatrixLight,
        MultiZoneLight,
    )

_LOGGER = logging.getLogger(__name__)


@dataclass
class DeviceVersion:
    """Device version information.

    Attributes:
        vendor: Vendor ID (typically 1 for LIFX)
        product: Product ID (identifies specific device model)
    """

    vendor: int
    product: int


@dataclass
class DeviceInfo:
    """Device runtime information.

    Attributes:
        time: Current device time (nanoseconds since epoch)
        uptime: Time since last power on (nanoseconds)
        downtime: Time device was powered off (nanoseconds)
    """

    time: int
    uptime: int
    downtime: int


@dataclass
class WifiInfo:
    """Device WiFi module information.

    Attributes:
        signal: WiFi signal strength
        rssi: WiFi RSSI
    """

    signal: float
    rssi: int = field(init=False)

    def __post_init__(self) -> None:
        """Calculate RSSI from signal."""
        self.rssi = int(floor(10 * log10(self.signal) + 0.5))


@dataclass
class FirmwareInfo:
    """Device firmware version information.

    Attributes:
        build: Firmware build timestamp
        version_major: Major version number
        version_minor: Minor version number
    """

    build: int
    version_major: int
    version_minor: int

    @property
    def as_dict(self) -> dict[str, int]:
        """Return firmware info as dict."""
        return {
            "version_major": self.version_major,
            "version_minor": self.version_minor,
        }


@dataclass
class CollectionInfo:
    """Device location and group collection information.

    Attributes:
        uuid: Collection UUID (16 hexadecimal characters)
        label: Collection label (up to 32 characters)
        updated_at: Timestamp when group was last updated (nanoseconds)
    """

    uuid: str
    label: str
    updated_at: int

    @property
    def as_dict(self) -> dict[str, str | int]:
        """Return group info as dict."""
        return {"uuid": self.uuid, "label": self.label, "updated_at": self.updated_at}


@dataclass
class DeviceCapabilities:
    """Device capabilities from product registry.

    Attributes:
        has_color: Supports color control
        has_multizone: Supports multizone control (strips, beams)
        has_chain: Supports chaining (tiles)
        has_matrix: Supports 2D matrix control (tiles, candle, path)
        has_infrared: Supports infrared LED
        has_hev: Supports HEV (High Energy Visible) cleaning cycles
        has_extended_multizone: Supports extended multizone protocol
        kelvin_min: Minimum color temperature (Kelvin)
        kelvin_max: Maximum color temperature (Kelvin)
    """

    has_color: bool
    has_multizone: bool
    has_chain: bool
    has_matrix: bool
    has_infrared: bool
    has_hev: bool
    has_extended_multizone: bool
    kelvin_min: int | None
    kelvin_max: int | None

    @property
    def has_variable_color_temp(self) -> bool:
        """Check if device supports variable color temperature."""
        return (
            self.kelvin_min is not None
            and self.kelvin_max is not None
            and self.kelvin_min != self.kelvin_max
        )

    @property
    def as_dict(self) -> dict[str, bool | int]:
        """Return DeviceCapabilities as a dict."""
        return {
            "has_color": self.has_color,
            "has_multizone": self.has_multizone,
            "has_extended_multizone": self.has_extended_multizone,
            "has_chain": self.has_chain,
            "has_matrix": self.has_matrix,
            "has_infrared": self.has_infrared,
            "has_hev": self.has_hev,
            "has_variable_color_temp": self.has_variable_color_temp,
            "kelvin_max": self.kelvin_max if self.kelvin_max is not None else 9000,
            "kelvin_min": self.kelvin_min if self.kelvin_min is not None else 1500,
        }


@dataclass
class DeviceState:
    """Base device state.

    Attributes:
        model: Friendly product name (e.g., "LIFX A19")
        label: Device label (user-assigned name)
        serial: Device serial number (6 bytes)
        mac_address: Device MAC address (formatted string)
        capabilities: Device capabilities from product registry
        power: Power level (0 = off, 65535 = on)
        host_firmware: Host firmware version
        wifi_firmware: WiFi firmware version
        location: Location tuple (UUID bytes, label, updated_at)
        group: Group tuple (UUID bytes, label, updated_at)
        last_updated: Timestamp of last state refresh
    """

    model: str
    label: str
    serial: str
    mac_address: str
    capabilities: DeviceCapabilities
    power: int
    host_firmware: FirmwareInfo
    wifi_firmware: FirmwareInfo
    location: CollectionInfo
    group: CollectionInfo
    last_updated: float

    @property
    def as_dict(
        self,
    ) -> dict[str, str | int | float | dict[str, bool | int] | dict[str, str | int]]:
        """Return DeviceState as a dictionary."""
        return {
            "model": self.model,
            "label": self.label,
            "serial": self.serial,
            "mac_address": self.mac_address,
            "capabilities": self.capabilities.as_dict,
            "power": self.power,
            "host_firmware": self.host_firmware.as_dict,
            "wifi_firmware": self.wifi_firmware.as_dict,
            "location": self.location.as_dict,
            "group": self.group.as_dict,
            "last_updated": self.last_updated,
        }

    @property
    def is_on(self) -> bool:
        """Check if device is powered on."""
        return self.power > 0

    @property
    def location_name(self) -> str:
        """Get location label."""
        return self.location.label

    @property
    def group_name(self) -> str:
        """Get group label."""
        return self.group.label

    @property
    def age(self) -> float:
        """Get age of state in seconds."""
        import time

        return time.time() - self.last_updated

    def is_fresh(self, max_age: float = 5.0) -> bool:
        """Check if state is fresh (recently updated).

        Args:
            max_age: Maximum age in seconds (default: 5.0)

        Returns:
            True if state age is less than max_age
        """
        return self.age < max_age


# TypeVar for generic state type, bound to DeviceState
StateT = TypeVar("StateT", bound=DeviceState)


class Device(Generic[StateT]):
    """Base class for LIFX devices.

    This class provides common functionality for all LIFX devices:
    - Connection management
    - Basic device queries (label, power, version, info)
    - State caching for reduced network traffic

    Properties return cached values or None if never fetched.
    Use get_*() methods to fetch fresh data from the device.

    Example:
        ```python
        device = Device(serial="d073d5123456", ip="192.168.1.100")

        async with device:
            # Get device label
            label = await device.get_label()
            print(f"Device: {label}")

            # Use cached label value
            if device.label is not None:
                print(f"Cached label: {device.label}")

            # Turn on device
            await device.set_power(True)

            # Get power state
            is_on = await device.get_power()
            if is_on is not None:
                print(f"Power: {'ON' if is_on else 'OFF'}")
        ```
    """

    @staticmethod
    def _raise_if_unhandled(response: object) -> None:
        """Raise LifxUnsupportedCommandError if device doesn't support the command.

        Args:
            response: The response from connection.request()

        Raises:
            LifxUnsupportedCommandError: If response is StateUnhandled or False
        """
        if isinstance(response, packets.Device.StateUnhandled):
            raise LifxUnsupportedCommandError(
                f"Device does not support packet type {response.unhandled_type}"
            )

    def __init__(
        self,
        serial: str,
        ip: str,
        port: int = LIFX_UDP_PORT,
        timeout: float = DEFAULT_REQUEST_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        """Initialize device.

        Args:
            serial: Device serial number as 12-digit hex string (e.g., "d073d5123456")
            ip: Device IP address
            port: Device UDP port
            timeout: Overall timeout for network requests in seconds
            max_retries: Maximum number of retry attempts for network requests

        Raises:
            ValueError: If any parameter is invalid
        """
        # Parse and validate serial number
        try:
            serial_obj = Serial.from_string(serial)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid serial number: {e}") from e

        serial_bytes = serial_obj.value

        # Validate serial number
        # Check for all-zeros (invalid)
        if serial_bytes == b"\x00" * 6:
            raise ValueError("Serial number cannot be all zeros")  # pragma: no cover

        # Check for all-ones/broadcast (invalid for unicast)
        if serial_bytes == b"\xff" * 6:
            raise ValueError(  # pragma: no cover
                "Broadcast serial number not allowed for device connection"
            )

        # Validate IP address
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError as e:  # pragma: no cover
            raise ValueError(f"Invalid IP address format: {e}")

        # Check for localhost
        if addr.is_loopback:
            # raise ValueError("Localhost IP address not allowed")  # pragma: no cover
            _LOGGER.warning(
                {
                    "class": "Device",
                    "method": "__init__",
                    "action": "is_loopback",
                    "ip": ip,
                }
            )

        # Check for unspecified (0.0.0.0)
        if addr.is_unspecified:
            raise ValueError(
                "Unspecified IP address (0.0.0.0) not allowed"
            )  # pragma: no cover

        # Warn for non-private IPs (LIFX should be on local network)
        if not addr.is_private:
            _LOGGER.warning(
                {
                    "class": "Device",
                    "method": "__init__",
                    "action": "non_private_ip",
                    "ip": ip,
                }
            )

        # LIFX uses IPv4 only (protocol limitation)
        if addr.version != 4:
            raise ValueError("Only IPv4 addresses are supported")  # pragma: no cover

        # Validate port
        if not (1024 <= port <= 65535):
            raise ValueError(
                f"Port must be between 1 and 65535, got {port}"
            )  # pragma: no cover

        # Warn for non-standard ports
        if port != LIFX_UDP_PORT:
            _LOGGER.warning(
                {
                    "class": "Device",
                    "method": "__init__",
                    "action": "non_standard_port",
                    "port": port,
                    "default_port": LIFX_UDP_PORT,
                }
            )

        # Store normalized serial as 12-digit hex string
        self.serial = serial_obj.to_string()
        self.ip = ip
        self.port = port
        self._timeout = timeout
        self._max_retries = max_retries

        # Create lightweight connection handle - connection pooling is internal
        self.connection = DeviceConnection(
            serial=self.serial,
            ip=self.ip,
            port=self.port,
            timeout=timeout,
            max_retries=max_retries,
        )

        # State storage: Cached values from device
        self._label: str | None = None
        self._version: DeviceVersion | None = None
        self._host_firmware: FirmwareInfo | None = None
        self._wifi_firmware: FirmwareInfo | None = None
        self._location: CollectionInfo | None = None
        self._group: CollectionInfo | None = None
        self._mac_address: str | None = None

        # Product capabilities for device features (populated on first use)
        self._capabilities: ProductInfo | None = None

        # State management (populated by connect() factory or _initialize_state())
        self._state: StateT | None = None
        self._refresh_task: asyncio.Task[None] | None = None
        self._refresh_lock = asyncio.Lock()
        self._is_closed = False

    @classmethod
    async def from_ip(
        cls,
        ip: str,
        port: int = LIFX_UDP_PORT,
        serial: str | None = None,
        timeout: float = DEFAULT_REQUEST_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> Self:
        """Create and return an instance for the given IP address.

        This is a convenience class method for connecting to a known device
        by IP address. The returned instance can be used as a context manager.

        Args:
            ip: IP address of the device
            port: Port number (default LIFX_UDP_PORT)
            serial: Serial number as 12-digit hex string
            timeout: Request timeout for this device instance

        Returns:
            Device instance ready to use with async context manager

        Example:
            ```python
            async with await Device.from_ip(ip="192.168.1.100") as device:
                label = await device.get_label()
            ```
        """
        if serial is None:
            temp_conn = DeviceConnection(
                serial="000000000000",
                ip=ip,
                port=port,
                timeout=timeout,
                max_retries=max_retries,
            )
            try:
                response = await temp_conn.request(
                    packets.Device.GetService(), timeout=timeout
                )
                if response and isinstance(response, packets.Device.StateService):
                    if temp_conn.serial and temp_conn.serial != "000000000000":
                        return cls(
                            serial=temp_conn.serial,
                            ip=ip,
                            port=port,
                            timeout=timeout,
                            max_retries=max_retries,
                        )
            finally:
                # Always close the temporary connection to prevent resource leaks
                await temp_conn.close()
        else:
            return cls(
                serial=serial,
                ip=ip,
                port=port,
                timeout=timeout,
                max_retries=max_retries,
            )

        raise LifxDeviceNotFoundError()

    @classmethod
    async def connect(
        cls,
        ip: str,
        serial: str | None = None,
        port: int = LIFX_UDP_PORT,
        timeout: float = DEFAULT_REQUEST_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> Light | HevLight | InfraredLight | MultiZoneLight | MatrixLight | CeilingLight:
        """Create and return a fully initialized device instance.

        This factory method creates the appropriate device type (Light, etc)
        based on the device's capabilities and initializes its state. The returned
        device MUST be used with an async context manager.

        The returned device subclass has guaranteed initialized state - the state
        property will never be None for devices created via this method.

        Args:
            ip: IP address of the device
            serial: Optional serial number (12-digit hex, with or without colons).
                    If None, queries device to get serial.
            port: Port number (default LIFX_UDP_PORT)
            timeout: Request timeout for this device instance
            max_retries: Maximum number of retry attempts

        Returns:
            Fully initialized device instance (Light, MultiZoneLight, MatrixLight, etc.)
            with complete state loaded and guaranteed non-None state property.

        Raises:
            LifxDeviceNotFoundError: If device cannot be found or contacted
            LifxTimeoutError: If device does not respond
            ValueError: If serial format is invalid

        Example:
            ```python
            # Connect by IP (serial auto-detected)
            device = await Device.connect(ip="192.168.1.100")
            async with device:
                # device.state is guaranteed to be initialized
                print(f"{device.state.model}: {device.state.label}")
                if device.state.is_on:
                    print("Device is on")

            # Connect with known serial
            device = await Device.connect(ip="192.168.1.100", serial="d073d5123456")
            async with device:
                await device.set_power(True)
            ```
        """
        # Step 1: Get serial if not provided
        if serial is None:
            temp_conn = DeviceConnection(
                serial="000000000000",
                ip=ip,
                port=port,
                timeout=timeout,
                max_retries=max_retries,
            )
            try:
                response = await temp_conn.request(
                    packets.Device.GetService(), timeout=timeout
                )
                if response and isinstance(response, packets.Device.StateService):
                    if temp_conn.serial and temp_conn.serial != "000000000000":
                        serial = temp_conn.serial
                    else:
                        raise LifxDeviceNotFoundError(
                            "Could not determine device serial"
                        )
                else:
                    raise LifxDeviceNotFoundError("No response from device")
            finally:
                await temp_conn.close()

        # Step 2: Normalize serial (accept with or without colons)
        serial = serial.replace(":", "")

        # Step 3: Create temporary device to get product info
        temp_device = cls(
            serial=serial,
            ip=ip,
            port=port,
            timeout=timeout,
            max_retries=max_retries,
        )

        try:
            # Get version to determine product
            version = await temp_device.get_version()
            product_info = get_product(version.product)

            if product_info is None:
                raise LifxDeviceNotFoundError(f"Unknown product ID: {version.product}")

            # Step 4: Determine correct device class based on capabilities
            # Import device classes here to avoid circular imports
            from typing import TYPE_CHECKING

            if TYPE_CHECKING:
                from lifx.devices.hev import HevLight
                from lifx.devices.infrared import InfraredLight
                from lifx.devices.light import Light
                from lifx.devices.matrix import MatrixLight
                from lifx.devices.multizone import MultiZoneLight

            device_class: type[Device] = cls

            # Check for ceiling products first (subset of matrix devices)
            from lifx.products import is_ceiling_product

            if is_ceiling_product(version.product):
                from lifx.devices.ceiling import CeilingLight

                device_class = CeilingLight
            elif product_info.has_matrix:
                from lifx.devices.matrix import MatrixLight

                device_class = MatrixLight
            elif product_info.has_multizone:
                from lifx.devices.multizone import MultiZoneLight

                device_class = MultiZoneLight
            elif product_info.has_infrared:
                from lifx.devices.infrared import InfraredLight

                device_class = InfraredLight
            elif product_info.has_hev:
                from lifx.devices.hev import HevLight

                device_class = HevLight
            elif product_info.has_color:
                from lifx.devices.light import Light

                device_class = Light

            # Step 5: Create instance of correct device class
            device = device_class(
                serial=serial,
                ip=ip,
                port=port,
                timeout=timeout,
                max_retries=max_retries,
            )

            # Type system note: device._state is guaranteed non-None after
            # _initialize_state().
            # Each subclass overrides _state to be non-optional
            return device  # type: ignore[return-value]

        finally:
            # Clean up temporary device
            await temp_device.connection.close()

    async def __aenter__(self) -> Self:
        """Enter async context manager."""
        await self._initialize_state()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Exit async context manager and close connection."""
        # Close device (cancels refresh tasks and connection)
        await self.close()

    async def _setup(self) -> None:
        """Populate device capabilities, state and metadata."""
        await self._ensure_capabilities()
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self.get_host_firmware())
            tg.create_task(self.get_wifi_firmware())
            tg.create_task(self.get_label())
            tg.create_task(self.get_location())
            tg.create_task(self.get_group())

    async def get_mac_address(self) -> str:
        """Calculate and return the MAC address for this device."""
        if self._mac_address is None:
            firmware = (
                self._host_firmware
                if self._host_firmware is not None
                else await self.get_host_firmware()
            )
            octets = [
                int(self.serial[i : i + 2], 16) for i in range(0, len(self.serial), 2)
            ]

            if firmware.version_major == 3:
                octets[5] = (octets[5] + 1) % 256

            self._mac_address = ":".join(f"{octet:02x}" for octet in octets)

        return self._mac_address

    async def _ensure_capabilities(self) -> None:
        """Ensure device capabilities are populated.

        This fetches the device version and firmware to determine product capabilities.
        If the device claims extended_multizone support but firmware is too old,
        the capability is removed.

        Called automatically when entering context manager, but can be called manually.
        """
        if self._capabilities is not None:  # pragma: no cover
            return

        # Get device version to determine product ID
        version = await self.get_version()
        self._capabilities = get_product(version.product)

        # If device has extended_multizone with minimum firmware requirement, verify it
        if self._capabilities and self._capabilities.has_extended_multizone:
            if self._capabilities.min_ext_mz_firmware is not None:
                firmware = await self.get_host_firmware()
                firmware_version = (
                    firmware.version_major << 16
                ) | firmware.version_minor

                # If firmware is too old, remove the extended_multizone capability
                if (
                    firmware_version < self._capabilities.min_ext_mz_firmware
                ):  # pragma: no cover
                    from lifx.products.registry import ProductCapability

                    self._capabilities.capabilities &= (
                        ~ProductCapability.EXTENDED_MULTIZONE
                    )

    @property
    def capabilities(self) -> ProductInfo | None:
        """Get device product capabilities.

        Returns product information including supported features like:
        - color, infrared, multizone, extended_multizone
        - matrix (for tiles), chain, relays, buttons, hev
        - temperature_range

        Capabilities are automatically loaded when using device as context manager.

        Returns:
            ProductInfo if capabilities have been loaded, None otherwise.

        Example:
            ```python
            async with device:
                if device.capabilities and device.capabilities.has_multizone:
                    print("Device supports multizone")
                if device.capabilities and device.capabilities.has_extended_multizone:
                    print("Device supports extended multizone")
            ```
        """
        return self._capabilities

    async def get_label(self) -> str:
        """Get device label/name.

        Always fetches from device. Use the `label` property to access stored value.

        Returns:
            Device label as string (max 32 bytes UTF-8)

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxProtocolError: If response is invalid
            LifxUnsupportedCommandError: If device doesn't support this command

        Example:
            ```python
            label = await device.get_label()
            print(f"Device name: {label}")

            # Or use cached value
            if device.label:
                print(f"Cached label: {device.label}")
            ```
        """
        # Request automatically unpacks and decodes label
        state = await self.connection.request(packets.Device.GetLabel())
        self._raise_if_unhandled(state)

        # Store label
        label_value = state.label
        self._label = label_value
        # Update state if it exists
        if self._state is not None:
            self._state.label = label_value
            self._state.last_updated = __import__("time").time()

        _LOGGER.debug(
            {
                "class": "Device",
                "method": "get_label",
                "action": "query",
                "reply": {"label": label_value},
            }
        )
        return label_value

    async def set_label(self, label: str) -> None:
        """Set device label/name.

        Args:
            label: New device label (max 32 bytes UTF-8)

        Raises:
            ValueError: If label is too long
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxUnsupportedCommandError: If device doesn't support this command

        Example:
            ```python
            # Set label
            await device.set_label("Living Room Light")
            ```
        """
        # Encode and pad to 32 bytes
        label_bytes = label.encode("utf-8")
        if len(label_bytes) > 32:
            raise ValueError(f"Label too long: {len(label_bytes)} bytes (max 32)")

        # Pad with zeros
        label_bytes = label_bytes.ljust(32, b"\x00")

        # Request automatically handles acknowledgement
        result = await self.connection.request(
            packets.Device.SetLabel(label=label_bytes),
        )
        self._raise_if_unhandled(result)

        if result:
            self._label = label

            if self._state is not None:
                self._state.label = label
                await self._schedule_refresh()

        _LOGGER.debug(
            {
                "class": "Device",
                "method": "set_label",
                "action": "change",
                "values": {"label": label},
            }
        )

    async def get_power(self) -> int:
        """Get device power state.

        Always fetches from device.

        Returns:
            Power level as integer (0 for off, 65535 for on)

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxProtocolError: If response is invalid
            LifxUnsupportedCommandError: If device doesn't support this command

        Example:
            ```python
            level = await device.get_power()
            print(f"Power: {'ON' if level > 0 else 'OFF'}")
            ```
        """
        # Request automatically unpacks response
        state = await self.connection.request(packets.Device.GetPower())
        self._raise_if_unhandled(state)

        # Power level is uint16 (0 or 65535)
        power_level = state.level
        # Update state if it exists
        if self._state is not None:
            self._state.power = power_level
            self._state.last_updated = __import__("time").time()

        _LOGGER.debug(
            {
                "class": "Device",
                "method": "get_power",
                "action": "query",
                "reply": {"level": power_level},
            }
        )
        return power_level

    async def set_power(self, level: bool | int) -> None:
        """Set device power state.

        Args:
            level: True/65535 to turn on, False/0 to turn off

        Raises:
            ValueError: If integer value is not 0 or 65535
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxUnsupportedCommandError: If device doesn't support this command

        Example:
            ```python
            # Turn on device with boolean
            await device.set_power(True)

            # Turn on device with integer
            await device.set_power(65535)

            # Turn off device
            await device.set_power(False)
            await device.set_power(0)
            ```
        """
        # Power level: 0 for off, 65535 for on
        if isinstance(level, bool):
            power_level = 65535 if level else 0
        elif isinstance(level, int):
            if level not in (0, 65535):
                raise ValueError(f"Power level must be 0 or 65535, got {level}")
            power_level = level

        # Request automatically handles acknowledgement
        result = await self.connection.request(
            packets.Device.SetPower(level=power_level),
        )
        self._raise_if_unhandled(result)

        _LOGGER.debug(
            {
                "class": "Device",
                "method": "set_power",
                "action": "change",
                "values": {"level": power_level},
            }
        )

        if result and self._state is not None:
            await self._schedule_refresh()

    async def get_version(self) -> DeviceVersion:
        """Get device version information.

        Always fetches from device.

        Returns:
            DeviceVersion with vendor and product fields

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxProtocolError: If response is invalid
            LifxUnsupportedCommandError: If device doesn't support this command

        Example:
            ```python
            version = await device.get_version()
            print(f"Vendor: {version.vendor}, Product: {version.product}")
            ```
        """
        # Request automatically unpacks response
        state = await self.connection.request(packets.Device.GetVersion())
        self._raise_if_unhandled(state)

        version = DeviceVersion(
            vendor=state.vendor,
            product=state.product,
        )

        self._version = version

        _LOGGER.debug(
            {
                "class": "Device",
                "method": "get_version",
                "action": "query",
                "reply": {"vendor": state.vendor, "product": state.product},
            }
        )
        return version

    async def get_info(self) -> DeviceInfo:
        """Get device runtime information.

        Always fetches from device.

        Returns:
            DeviceInfo with time, uptime, and downtime

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxProtocolError: If response is invalid
            LifxUnsupportedCommandError: If device doesn't support this command

        Example:
            ```python
            info = await device.get_info()
            uptime_hours = info.uptime / 1e9 / 3600
            print(f"Uptime: {uptime_hours:.1f} hours")
            ```
        """
        # Request automatically unpacks response
        state = await self.connection.request(packets.Device.GetInfo())  # type: ignore
        self._raise_if_unhandled(state)

        info = DeviceInfo(time=state.time, uptime=state.uptime, downtime=state.downtime)

        _LOGGER.debug(
            {
                "class": "Device",
                "method": "get_info",
                "action": "query",
                "reply": {
                    "time": state.time,
                    "uptime": state.uptime,
                    "downtime": state.downtime,
                },
            }
        )
        return info

    async def get_wifi_info(self) -> WifiInfo:
        """Get device WiFi module information.

        Always fetches from device.

        Returns:
            WifiInfo with signal strength and RSSI

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxProtocolError: If response is invalid
            LifxUnsupportedCommandError: If device doesn't support this command

        Example:
            ```python
            wifi_info = await device.get_wifi_info()
            print(f"WiFi signal: {wifi_info.signal}")
            print(f"WiFi RSSI: {wifi_info.rssi}")
            ```
        """
        # Request WiFi info from device
        state = await self.connection.request(packets.Device.GetWifiInfo())
        self._raise_if_unhandled(state)

        # Extract WiFi info from response
        wifi_info = WifiInfo(signal=state.signal)

        _LOGGER.debug(
            {
                "class": "Device",
                "method": "get_wifi_info",
                "action": "query",
                "reply": {"signal": state.signal},
            }
        )
        return wifi_info

    async def get_host_firmware(self) -> FirmwareInfo:
        """Get device host (WiFi module) firmware information.

        Always fetches from device.

        Returns:
            FirmwareInfo with build timestamp and version

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxProtocolError: If response is invalid
            LifxUnsupportedCommandError: If device doesn't support this command

        Example:
            ```python
            firmware = await device.get_host_firmware()
            print(f"Firmware: v{firmware.version_major}.{firmware.version_minor}")
            ```
        """
        # Request automatically unpacks response
        state = await self.connection.request(packets.Device.GetHostFirmware())  # type: ignore
        self._raise_if_unhandled(state)

        firmware = FirmwareInfo(
            build=state.build,
            version_major=state.version_major,
            version_minor=state.version_minor,
        )

        self._host_firmware = firmware

        # Calculate MAC address now that we have firmware info
        if self.mac_address is None:
            await self.get_mac_address()

        _LOGGER.debug(
            {
                "class": "Device",
                "method": "get_host_firmware",
                "action": "query",
                "reply": {
                    "build": state.build,
                    "version_major": state.version_major,
                    "version_minor": state.version_minor,
                },
            }
        )
        return firmware

    async def get_wifi_firmware(self) -> FirmwareInfo:
        """Get device WiFi module firmware information.

        Always fetches from device.

        Returns:
            FirmwareInfo with build timestamp and version

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxProtocolError: If response is invalid
            LifxUnsupportedCommandError: If device doesn't support this command

        Example:
            ```python
            wifi_fw = await device.get_wifi_firmware()
            print(f"WiFi Firmware: v{wifi_fw.version_major}.{wifi_fw.version_minor}")
            ```
        """
        # Request automatically unpacks response
        state = await self.connection.request(packets.Device.GetWifiFirmware())  # type: ignore
        self._raise_if_unhandled(state)

        firmware = FirmwareInfo(
            build=state.build,
            version_major=state.version_major,
            version_minor=state.version_minor,
        )

        self._wifi_firmware = firmware

        _LOGGER.debug(
            {
                "class": "Device",
                "method": "get_wifi_firmware",
                "action": "query",
                "reply": {
                    "build": state.build,
                    "version_major": state.version_major,
                    "version_minor": state.version_minor,
                },
            }
        )
        return firmware

    async def get_location(self) -> CollectionInfo:
        """Get device location information.

        Always fetches from device.

        Returns:
            CollectionInfo with location UUID, label, and updated timestamp

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxProtocolError: If response is invalid
            LifxUnsupportedCommandError: If device doesn't support this command

        Example:
            ```python
            location = await device.get_location()
            print(f"Location: {location.label}")
            print(f"Location ID: {location.uuid}")
            ```
        """
        # Request automatically unpacks response
        state = await self.connection.request(packets.Device.GetLocation())  # type: ignore
        self._raise_if_unhandled(state)

        location = CollectionInfo(
            uuid=state.location.hex(),
            label=state.label,
            updated_at=state.updated_at,
        )

        self._location = location
        if self._state is not None:
            self._state.location = location

        _LOGGER.debug(
            {
                "class": "Device",
                "method": "get_location",
                "action": "query",
                "reply": {
                    "location": state.location.hex(),
                    "label": state.label,
                    "updated_at": state.updated_at,
                },
            }
        )
        return location

    async def set_location(
        self, label: str, *, discover_timeout: float = DISCOVERY_TIMEOUT
    ) -> None:
        """Set device location information.

        Automatically discovers devices on the network to check if any device already
        has the target location label. If found, reuses that existing UUID to ensure
        devices with the same label share the same location UUID. If not found,
        generates a new UUID for this label.

        Args:
            label: Location label (max 32 characters)
            discover_timeout: Timeout for device discovery in seconds

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            ValueError: If label is invalid
            LifxUnsupportedCommandError: If device doesn't support this command

        Example:
            ```python
            # Set device location
            await device.set_location("Living Room")

            # If another device already has "Kitchen" location, this device will
            # join that existing location UUID
            await device.set_location("Kitchen")
            ```
        """
        # Validate label
        if not label:
            raise ValueError("Label cannot be empty")
        if len(label) > 32:
            raise ValueError(f"Label must be max 32 characters, got {len(label)}")

        # Import here to avoid circular dependency
        from lifx.network.discovery import discover_devices

        # Discover all devices to check for existing label
        location_uuid_to_use: bytes | None = None

        try:
            # Check each device for the target label
            async for disc in discover_devices(
                timeout=discover_timeout,
                device_timeout=self._timeout,
                max_retries=self._max_retries,
            ):
                temp_conn = DeviceConnection(
                    serial=disc.serial,
                    ip=disc.ip,
                    port=disc.port,
                    timeout=self._timeout,
                    max_retries=self._max_retries,
                )

                try:
                    # Get location info using new request() API
                    state_packet = await temp_conn.request(packets.Device.GetLocation())  # type: ignore

                    # Check if this device has the target label
                    if (
                        state_packet.label == label
                        and state_packet.location is not None
                        and isinstance(state_packet.location, bytes)
                    ):
                        location_uuid_to_use = state_packet.location
                        assert location_uuid_to_use is not None
                        # Type narrowing: we know location_uuid_to_use is not None here
                        _LOGGER.debug(
                            {
                                "action": "device.set_location",
                                "location_found": True,
                                "label": label,
                                "uuid": location_uuid_to_use.hex(),
                            }
                        )
                        break

                except Exception as e:
                    _LOGGER.debug(
                        {
                            "action": "device.set_location",
                            "discovery_query_failed": True,
                            "reason": str(e),
                        }
                    )
                    continue

                finally:
                    # Always close the temporary connection to prevent resource leaks
                    await temp_conn.close()

        except Exception as e:
            _LOGGER.warning(
                {
                    "warning": "Discovery failed, will generate new UUID",
                    "reason": str(e),
                }
            )

        # If no existing location with target label found, generate new UUID
        if location_uuid_to_use is None:
            location_uuid = uuid.uuid5(LIFX_LOCATION_NAMESPACE, label)
            location_uuid_to_use = location_uuid.bytes

        # Encode label for protocol
        label_bytes = label.encode("utf-8")[:32].ljust(32, b"\x00")

        # Always use current time as updated_at timestamp
        updated_at = int(time.time() * 1e9)

        # Update this device
        result = await self.connection.request(
            packets.Device.SetLocation(
                location=location_uuid_to_use, label=label_bytes, updated_at=updated_at
            ),
        )
        self._raise_if_unhandled(result)

        if result:
            self._location = CollectionInfo(
                uuid=location_uuid_to_use.hex(), label=label, updated_at=updated_at
            )

        if result and self._state is not None:
            self._state.location.uuid = location_uuid_to_use.hex()
            self._state.location.label = label
            self._state.location.updated_at = updated_at
            await self._schedule_refresh()

        _LOGGER.debug(
            {
                "class": "Device",
                "method": "set_location",
                "action": "change",
                "values": {
                    "location": location_uuid_to_use.hex(),
                    "label": label,
                    "updated_at": updated_at,
                },
            }
        )

    async def get_group(self) -> CollectionInfo:
        """Get device group information.

        Always fetches from device.

        Returns:
            CollectionInfo with group UUID, label, and updated timestamp

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxProtocolError: If response is invalid
            LifxUnsupportedCommandError: If device doesn't support this command

        Example:
            ```python
            group = await device.get_group()
            print(f"Group: {group.label}")
            print(f"Group ID: {group.uuid}")
            ```
        """
        # Request automatically unpacks response
        state = await self.connection.request(packets.Device.GetGroup())  # type: ignore
        self._raise_if_unhandled(state)

        group = CollectionInfo(
            uuid=state.group.hex(),
            label=state.label,
            updated_at=state.updated_at,
        )

        self._group = group
        if self._state is not None:
            self._state.group = group

        _LOGGER.debug(
            {
                "class": "Device",
                "method": "get_group",
                "action": "query",
                "reply": {
                    "uuid": state.group.hex(),
                    "label": state.label,
                    "updated_at": state.updated_at,
                },
            }
        )
        return group

    async def set_group(
        self, label: str, *, discover_timeout: float = DISCOVERY_TIMEOUT
    ) -> None:
        """Set device group information.

        Automatically discovers devices on the network to check if any device already
        has the target group label. If found, reuses that existing UUID to ensure
        devices with the same label share the same group UUID. If not found,
        generates a new UUID for this label.

        Args:
            label: Group label (max 32 characters)
            discover_timeout: Timeout for device discovery in seconds

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            ValueError: If label is invalid
            LifxUnsupportedCommandError: If device doesn't support this command

        Example:
            ```python
            # Set device group
            await device.set_group("Bedroom Lights")

            # If another device already has "Upstairs" group, this device will
            # join that existing group UUID
            await device.set_group("Upstairs")
            ```
        """
        # Validate label
        if not label:
            raise ValueError("Label cannot be empty")
        if len(label) > 32:
            raise ValueError(f"Label must be max 32 characters, got {len(label)}")

        # Import here to avoid circular dependency
        from lifx.network.discovery import discover_devices

        # Discover all devices to check for existing label
        group_uuid_to_use: bytes | None = None

        try:
            # Check each device for the target label
            async for disc in discover_devices(
                timeout=discover_timeout,
                device_timeout=self._timeout,
                max_retries=self._max_retries,
            ):
                temp_conn = DeviceConnection(
                    serial=disc.serial,
                    ip=disc.ip,
                    port=disc.port,
                    timeout=self._timeout,
                    max_retries=self._max_retries,
                )

                try:
                    # Get group info using new request() API
                    state_packet = await temp_conn.request(packets.Device.GetGroup())  # type: ignore

                    # Check if this device has the target label
                    if (
                        state_packet.label == label
                        and state_packet.group is not None
                        and isinstance(state_packet.group, bytes)
                    ):
                        group_uuid_to_use = state_packet.group
                        assert group_uuid_to_use is not None
                        # Type narrowing: we know group_uuid_to_use is not None here
                        _LOGGER.debug(
                            {
                                "action": "device.set_group",
                                "group_found": True,
                                "label": label,
                                "uuid": group_uuid_to_use.hex(),
                            }
                        )
                        break

                except Exception as e:
                    _LOGGER.debug(
                        {
                            "action": "device.set_group",
                            "discovery_query_failed": True,
                            "reason": str(e),
                        }
                    )
                    continue

                finally:
                    # Always close the temporary connection to prevent resource leaks
                    await temp_conn.close()

        except Exception as e:
            _LOGGER.warning(
                {
                    "warning": "Discovery failed, will generate new UUID",
                    "reason": str(e),
                }
            )

        # If no existing group with target label found, generate new UUID
        if group_uuid_to_use is None:
            group_uuid = uuid.uuid5(LIFX_GROUP_NAMESPACE, label)
            group_uuid_to_use = group_uuid.bytes

        # Encode label for protocol
        label_bytes = label.encode("utf-8")[:32].ljust(32, b"\x00")

        # Always use current time as updated_at timestamp
        updated_at = int(time.time() * 1e9)

        # Update this device
        result = await self.connection.request(
            packets.Device.SetGroup(
                group=group_uuid_to_use, label=label_bytes, updated_at=updated_at
            ),
        )
        self._raise_if_unhandled(result)

        if result:
            self._group = CollectionInfo(
                uuid=group_uuid_to_use.hex(), label=label, updated_at=updated_at
            )

        if result and self._state is not None:
            self._state.location.uuid = group_uuid_to_use.hex()
            self._state.location.label = label
            self._state.location.updated_at = updated_at
            await self._schedule_refresh()

        _LOGGER.debug(
            {
                "class": "Device",
                "method": "set_group",
                "action": "change",
                "values": {
                    "group": group_uuid_to_use.hex(),
                    "label": label,
                    "updated_at": updated_at,
                },
            }
        )

    async def set_reboot(self) -> None:
        """Reboot the device.

        This sends a reboot command to the device. The device will disconnect
        and restart. You should disconnect from the device after calling this method.

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxUnsupportedCommandError: If device doesn't support this command

        Example:
            ```python
            async with device:
                await device.set_reboot()
                # Device will reboot, connection will be lost
            ```

        Note:
            After rebooting, you may need to wait 10-30 seconds before the device
            comes back online and is discoverable again.
        """
        # Send reboot request
        result = await self.connection.request(
            packets.Device.SetReboot(),
        )
        self._raise_if_unhandled(result)
        _LOGGER.debug(
            {
                "class": "Device",
                "method": "set_reboot",
                "action": "change",
                "values": {},
            }
        )

    async def close(self) -> None:
        """Close device connection and cleanup resources.

        Cancels any pending refresh tasks and closes the network connection.
        Called automatically when exiting the async context manager.
        """
        self._is_closed = True
        if self._refresh_task and not self._refresh_task.done():
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
        await self.connection.close()

    @property
    def state(self) -> StateT | None:
        """Get device state if available.

        State is populated by the connect() factory method or by calling
        _initialize_state() directly. Returns None if state has not been initialized.

        Returns:
            State with current device state, or None if not initialized
        """
        return self._state

    def _create_capabilities(self) -> DeviceCapabilities:
        """Create DeviceCapabilities instance from product registry.

        Returns:
            DeviceCapabilities instance

        Raises:
            RuntimeError: If capabilities have not been loaded
        """
        assert self._capabilities is not None
        product_info = self._capabilities

        return DeviceCapabilities(
            has_color=product_info.has_color,
            has_multizone=product_info.has_multizone,
            has_chain=product_info.has_chain,
            has_matrix=product_info.has_matrix,
            has_infrared=product_info.has_infrared,
            has_hev=product_info.has_hev,
            has_extended_multizone=product_info.has_extended_multizone,
            kelvin_min=(
                product_info.temperature_range.min
                if product_info.temperature_range
                else None
            ),
            kelvin_max=(
                product_info.temperature_range.max
                if product_info.temperature_range
                else None
            ),
        )

    async def _initialize_state(self) -> StateT:
        """Initialize device state transactionally.

        Fetches all required device state in parallel and creates the state instance.
        This is an all-or-nothing operation - either all state is fetched successfully
        or an exception is raised.

        Raises:
            LifxTimeoutError: If device does not respond within timeout
            LifxDeviceNotFoundError: If device cannot be reached
            LifxProtocolError: If responses are invalid
        """
        # Ensure capabilities are loaded
        await self._ensure_capabilities()
        capabilities = self._create_capabilities()

        # Fetch semi-static and volatile state in parallel
        # get_color returns color, power, and label in one request
        async with asyncio.TaskGroup() as tg:
            label_task = tg.create_task(self.get_label())
            power_task = tg.create_task(self.get_power())
            host_fw_task = tg.create_task(self.get_host_firmware())
            wifi_fw_task = tg.create_task(self.get_wifi_firmware())
            location_task = tg.create_task(self.get_location())
            group_task = tg.create_task(self.get_group())

        # Extract results
        label = label_task.result()
        power = power_task.result()
        host_firmware = host_fw_task.result()
        wifi_firmware = wifi_fw_task.result()
        location_info = location_task.result()
        group_info = group_task.result()

        # Get MAC address (already calculated in get_host_firmware)
        mac_address = await self.get_mac_address()

        # Get model name
        assert self._capabilities is not None
        model = self._capabilities.name

        # Create state instance
        # Cast is needed because when Device is used directly, StateT = DeviceState
        # Subclasses override this method to create their specific state type
        self._state = cast(
            StateT,
            DeviceState(
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
                last_updated=time.time(),
            ),
        )

        return self._state

    async def refresh_state(self) -> None:
        """Refresh device state from hardware.

        Fetches current state from device and updates the state instance.
        Base implementation fetches label, power, and updates timestamp.
        Subclasses override to add device-specific state updates.

        Raises:
            RuntimeError: If state has not been initialized
            LifxTimeoutError: If device does not respond
            LifxDeviceNotFoundError: If device cannot be reached
        """
        if not self._state:
            await self._initialize_state()
            return

    async def _schedule_refresh(self) -> None:
        """Schedule debounced state refresh.

        Schedules a refresh task that waits for STATE_REFRESH_DEBOUNCE_MS milliseconds
        before executing. If another refresh is scheduled before the delay expires,
        the previous task is cancelled and a new one is scheduled.

        This ensures that rapid state changes only trigger one refresh.
        """
        from lifx.const import STATE_REFRESH_DEBOUNCE_MS

        if self._is_closed:
            return

        # Cancel existing refresh task if running
        if self._refresh_task and not self._refresh_task.done():
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass

        # Schedule new refresh task
        async def _debounced_refresh() -> None:
            try:
                await asyncio.sleep(STATE_REFRESH_DEBOUNCE_MS / 1000.0)
                if not self._is_closed:
                    async with self._refresh_lock:
                        await self.refresh_state()
            except asyncio.CancelledError:
                pass
            except Exception as e:
                _LOGGER.warning(
                    {
                        "class": "Device",
                        "method": "_schedule_refresh",
                        "action": "refresh_failed",
                        "error": str(e),
                    }
                )

        self._refresh_task = asyncio.create_task(_debounced_refresh())

    @property
    def label(self) -> str | None:
        """Get cached label if available.

        Use get_label() to fetch from device.

        Returns:
            Device label or None if never fetched.
        """
        if self._state is not None:
            return self._state.label
        elif self._label is not None:
            return self._label
        return None

    @property
    def version(self) -> DeviceVersion | None:
        """Get cached version if available.

        Use get_version() to fetch from device.

        Returns:
            Device version or None if never fetched.
        """
        return self._version

    @property
    def host_firmware(self) -> FirmwareInfo | None:
        """Get cached host firmware if available.

        Use get_host_firmware() to fetch from device.

        Returns:
            Firmware info or None if never fetched.
        """
        if self._state is not None:
            return self._state.host_firmware
        elif self._host_firmware is not None:
            return self._host_firmware
        return None

    @property
    def wifi_firmware(self) -> FirmwareInfo | None:
        """Get cached wifi firmware if available.

        Use get_wifi_firmware() to fetch from device.

        Returns:
            Firmware info or None if never fetched.
        """
        if self._state is not None:
            return self._state.wifi_firmware
        elif self._wifi_firmware is not None:
            return self._wifi_firmware
        return None

    @property
    def location(self) -> str | None:
        """Get cached location name if available.

        Use get_location() to fetch from device.

        Returns:
            Location name or None if never fetched.
        """
        if self._state is not None:
            return self._state.location_name
        elif self._location is not None:
            return self._location.label
        return None

    @property
    def group(self) -> str | None:
        """Get cached group name if available.

        Use get_group() to fetch from device.

        Returns:
            Group name or None if never fetched.
        """
        if self._state is not None:
            return self._state.group_name
        elif self._group is not None:
            return self._group.label
        return None

    @property
    def model(self) -> str | None:
        """Get LIFX friendly model name if available.

        Returns:
            Model string from product registry.
        """
        if self._state is not None:
            return self._state.model
        elif self.capabilities is not None:
            return self.capabilities.name
        return None

    @property
    def mac_address(self) -> str | None:
        """Get cached MAC address if available.

        Use get_host_firmware() to calculate MAC address from device firmware.

        Returns:
            MAC address in colon-separated format (e.g., "d0:73:d5:01:02:03"),
            or None if not yet calculated.
        """
        if self._state is not None:
            return self._state.mac_address
        elif self._mac_address is not None:
            return self._mac_address
        return None

    def __repr__(self) -> str:
        """String representation of device."""
        return f"Device(serial={self.serial}, ip={self.ip}, port={self.port})"
