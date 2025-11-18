"""Base device class for LIFX devices."""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Self

from lifx.const import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_REQUEST_TIMEOUT,
    DISCOVERY_TIMEOUT,
    LIFX_GROUP_NAMESPACE,
    LIFX_LOCATION_NAMESPACE,
    LIFX_UDP_PORT,
)
from lifx.exceptions import LifxDeviceNotFoundError
from lifx.network.connection import DeviceConnection
from lifx.products.registry import ProductInfo, get_product
from lifx.protocol import packets
from lifx.protocol.models import Serial

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
        signal: WiFi signal strength (mW)
        tx: Bytes transmitted since power on
        rx: Bytes received since power on
    """

    signal: float
    tx: int
    rx: int


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


@dataclass
class LocationInfo:
    """Device location information.

    Attributes:
        location: Location UUID (16 bytes)
        label: Location label (up to 32 characters)
        updated_at: Timestamp when location was last updated (nanoseconds)
    """

    location: bytes
    label: str
    updated_at: int


@dataclass
class GroupInfo:
    """Device group information.

    Attributes:
        group: Group UUID (16 bytes)
        label: Group label (up to 32 characters)
        updated_at: Timestamp when group was last updated (nanoseconds)
    """

    group: bytes
    label: str
    updated_at: int


class Device:
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
        self._location: LocationInfo | None = None
        self._group: GroupInfo | None = None
        self._mac_address: str | None = None

        # Product capabilities for device features (populated on first use)
        self._capabilities: ProductInfo | None = None

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
            temp_conn = DeviceConnection(serial="000000000000", ip=ip, port=port)
            try:
                response = await temp_conn.request(
                    packets.Device.GetService(), timeout=DISCOVERY_TIMEOUT
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

    async def __aenter__(self) -> Self:
        """Enter async context manager."""
        # No connection setup needed - connection pool handles everything
        await self._setup()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Exit async context manager and close connection."""
        # Close connection for explicit cleanup
        await self.connection.close()

    async def _setup(self) -> None:
        """Populate device capabilities, state and metadata."""
        await self._ensure_capabilities()
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self.get_host_firmware())
            tg.create_task(self.get_wifi_firmware())
            tg.create_task(self.get_label())
            tg.create_task(self.get_location())
            tg.create_task(self.get_group())

    def _calculate_mac_address(self) -> None:
        """Calculate MAC address from serial and host firmware version.

        The MAC address calculation depends on the major version of the host firmware:
        - Version 2 or 4: MAC address matches the serial
        - Version 3: MAC address is serial with LSB + 1 (with wraparound from FF to 00)
        - Unknown versions: Default to serial

        This method is called automatically when host firmware is fetched.
        """
        if self._host_firmware is None:  # pragma: no cover
            return

        # Get serial bytes
        serial_obj = Serial.from_string(self.serial)
        serial_bytes = bytearray(serial_obj.value)

        # Check firmware major version
        major_version = self._host_firmware.version_major

        if major_version in (2, 4):
            # MAC address matches serial
            mac_bytes = bytes(serial_bytes)
        elif major_version == 3:
            # Add 1 to least significant byte (with wraparound)
            serial_bytes[5] = (serial_bytes[5] + 1) % 256
            mac_bytes = bytes(serial_bytes)
        else:
            # For unknown versions, default to serial
            mac_bytes = bytes(serial_bytes)

        # Convert to colon-separated hex string format (e.g., "d0:73:d5:01:02:03")
        self._mac_address = ":".join(f"{b:02x}" for b in mac_bytes)

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

        # Store label
        self._label = state.label
        _LOGGER.debug(
            {
                "class": "Device",
                "method": "get_label",
                "action": "query",
                "reply": {"label": state.label},
            }
        )
        return state.label

    async def set_label(self, label: str) -> None:
        """Set device label/name.

        Args:
            label: New device label (max 32 bytes UTF-8)

        Raises:
            ValueError: If label is too long
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond

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
        await self.connection.request(
            packets.Device.SetLabel(label=label_bytes),
        )

        # Update cached state
        self._label = label
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

        Example:
            ```python
            level = await device.get_power()
            print(f"Power: {'ON' if level > 0 else 'OFF'}")
            ```
        """
        # Request automatically unpacks response
        state = await self.connection.request(packets.Device.GetPower())

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

    async def set_power(self, level: bool | int) -> None:
        """Set device power state.

        Args:
            level: True/65535 to turn on, False/0 to turn off

        Raises:
            ValueError: If integer value is not 0 or 65535
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond

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
        else:
            raise TypeError(f"Expected bool or int, got {type(level).__name__}")

        # Request automatically handles acknowledgement
        await self.connection.request(
            packets.Device.SetPower(level=power_level),
        )

        _LOGGER.debug(
            {
                "class": "Device",
                "method": "set_power",
                "action": "change",
                "values": {"level": power_level},
            }
        )

    async def get_version(self) -> DeviceVersion:
        """Get device version information.

        Always fetches from device.

        Returns:
            DeviceVersion with vendor and product fields

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxProtocolError: If response is invalid

        Example:
            ```python
            version = await device.get_version()
            print(f"Vendor: {version.vendor}, Product: {version.product}")
            ```
        """
        # Request automatically unpacks response
        state = await self.connection.request(packets.Device.GetVersion())

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

        Example:
            ```python
            info = await device.get_info()
            uptime_hours = info.uptime / 1e9 / 3600
            print(f"Uptime: {uptime_hours:.1f} hours")
            ```
        """
        # Request automatically unpacks response
        state = await self.connection.request(packets.Device.GetInfo())  # type: ignore

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
            WifiInfo with signal strength and network stats

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxProtocolError: If response is invalid

        Example:
            ```python
            wifi_info = await device.get_wifi_info()
            print(f"WiFi signal: {wifi_info.signal} mW")
            print(f"TX: {wifi_info.tx} bytes, RX: {wifi_info.rx} bytes")
            ```
        """
        # Request WiFi info from device
        state = await self.connection.request(packets.Device.GetWifiInfo())

        # Extract WiFi info from response
        wifi_info = WifiInfo(signal=state.signal, tx=state.tx, rx=state.rx)

        _LOGGER.debug(
            {
                "class": "Device",
                "method": "get_wifi_info",
                "action": "query",
                "reply": {"signal": state.signal, "tx": state.tx, "rx": state.rx},
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

        Example:
            ```python
            firmware = await device.get_host_firmware()
            print(f"Firmware: v{firmware.version_major}.{firmware.version_minor}")
            ```
        """
        # Request automatically unpacks response
        state = await self.connection.request(packets.Device.GetHostFirmware())  # type: ignore

        firmware = FirmwareInfo(
            build=state.build,
            version_major=state.version_major,
            version_minor=state.version_minor,
        )

        self._host_firmware = firmware

        # Calculate MAC address now that we have firmware info
        self._calculate_mac_address()

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

        Example:
            ```python
            wifi_fw = await device.get_wifi_firmware()
            print(f"WiFi Firmware: v{wifi_fw.version_major}.{wifi_fw.version_minor}")
            ```
        """
        # Request automatically unpacks response
        state = await self.connection.request(packets.Device.GetWifiFirmware())  # type: ignore

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

    async def get_location(self) -> LocationInfo:
        """Get device location information.

        Always fetches from device.

        Returns:
            LocationInfo with location UUID, label, and updated timestamp

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxProtocolError: If response is invalid

        Example:
            ```python
            location = await device.get_location()
            print(f"Location: {location.label}")
            print(f"Location ID: {location.location.hex()}")
            ```
        """
        # Request automatically unpacks response
        state = await self.connection.request(packets.Device.GetLocation())  # type: ignore

        location = LocationInfo(
            location=state.location,
            label=state.label,
            updated_at=state.updated_at,
        )

        self._location = location

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
            async for disc in discover_devices(timeout=discover_timeout):
                temp_conn = DeviceConnection(
                    serial=disc.serial, ip=disc.ip, port=disc.port
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
        await self.connection.request(
            packets.Device.SetLocation(
                location=location_uuid_to_use, label=label_bytes, updated_at=updated_at
            ),
        )

        # Update cached state
        location_info = LocationInfo(
            location=location_uuid_to_use, label=label, updated_at=updated_at
        )
        self._location = location_info
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

    async def get_group(self) -> GroupInfo:
        """Get device group information.

        Always fetches from device.

        Returns:
            GroupInfo with group UUID, label, and updated timestamp

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxProtocolError: If response is invalid

        Example:
            ```python
            group = await device.get_group()
            print(f"Group: {group.label}")
            print(f"Group ID: {group.group.hex()}")
            ```
        """
        # Request automatically unpacks response
        state = await self.connection.request(packets.Device.GetGroup())  # type: ignore

        group = GroupInfo(
            group=state.group,
            label=state.label,
            updated_at=state.updated_at,
        )

        self._group = group

        _LOGGER.debug(
            {
                "class": "Device",
                "method": "get_group",
                "action": "query",
                "reply": {
                    "group": state.group.hex(),
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
            async for disc in discover_devices(timeout=discover_timeout):
                temp_conn = DeviceConnection(
                    serial=disc.serial, ip=disc.ip, port=disc.port
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
        await self.connection.request(
            packets.Device.SetGroup(
                group=group_uuid_to_use, label=label_bytes, updated_at=updated_at
            ),
        )

        # Update cached state
        group_info = GroupInfo(
            group=group_uuid_to_use, label=label, updated_at=updated_at
        )
        self._group = group_info
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
        await self.connection.request(
            packets.Device.SetReboot(),
        )
        _LOGGER.debug(
            {
                "class": "Device",
                "method": "set_reboot",
                "action": "change",
                "values": {},
            }
        )

    @property
    def label(self) -> str | None:
        """Get cached label if available.

        Use get_label() to fetch from device.

        Returns:
            Device label or None if never fetched.
        """
        return self._label

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
        return self._host_firmware

    @property
    def wifi_firmware(self) -> FirmwareInfo | None:
        """Get cached wifi firmware if available.

        Use get_wifi_firmware() to fetch from device.

        Returns:
            Firmware info or None if never fetched.
        """
        return self._wifi_firmware

    @property
    def location(self) -> str | None:
        """Get cached location name if available.

        Use get_location() to fetch from device.

        Returns:
            Location name or None if never fetched.
        """
        if self._location is not None:
            return self._location.label
        return None

    @property
    def group(self) -> str | None:
        """Get cached group name if available.

        Use get_group() to fetch from device.

        Returns:
            Group name or None if never fetched.
        """
        if self._group is not None:
            return self._group.label
        return None

    @property
    def model(self) -> str | None:
        """Get LIFX friendly model name if available.

        Returns:
            Model string from product registry.
        """
        if self.capabilities is not None:
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
        return self._mac_address

    def __repr__(self) -> str:
        """String representation of device."""
        return f"Device(serial={self.serial}, ip={self.ip}, port={self.port})"
