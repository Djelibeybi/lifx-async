"""Base device class for LIFX devices."""

from __future__ import annotations

import ipaddress
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any, ClassVar, Self

from lifx.const import (
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
    - State caching with TTL

    Example:
        ```python
        device = Device(serial="d073d5123456", ip="192.168.1.100")

        async with device:
            # Get device label
            label = await device.get_label()
            print(f"Device: {label}")

            # Turn on device
            await device.set_power(True)

            # Get power state
            is_on = await device.get_power()
            print(f"Power: {'ON' if is_on else 'OFF'}")
        ```
    """

    # Cache TTL bounds
    MIN_CACHE_TTL: ClassVar[float] = 0.1  # 100ms minimum
    MAX_CACHE_TTL: ClassVar[float] = 300.0  # 5 minutes maximum
    DEFAULT_CACHE_TTL: ClassVar[float] = 5.0

    # Cache TTL categories
    STATE_CACHE_TTL: ClassVar[float] = 5.0  # Short-lived: color, power, zones
    METADATA_CACHE_TTL: ClassVar[float] = (
        180.0  # Long-lived: label, version, info, etc.
    )
    PERMANENT_CACHE_TTL: ClassVar[float] = float(
        "inf"
    )  # Permanent: version, firmware, service, chain

    def __init__(
        self,
        serial: str,
        ip: str,
        port: int = LIFX_UDP_PORT,
        cache_ttl: float | None = None,
        timeout: float = 1.0,
        max_retries: int = 3,
    ) -> None:
        """Initialize device.

        Args:
            serial: Device serial number as 12-digit hex string (e.g., "d073d5123456")
            ip: Device IP address
            port: Device UDP port
            cache_ttl: Cache time-to-live in seconds (default 5.0, min 0.1, max 300)
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
            raise ValueError("Serial number cannot be all zeros")

        # Check for all-ones/broadcast (invalid for unicast)
        if serial_bytes == b"\xff" * 6:
            raise ValueError(
                "Broadcast serial number not allowed for device connection"
            )

        # Check multicast bit (first byte, LSB should be 0 for unicast)
        if serial_bytes[0] & 0x01:
            raise ValueError("Multicast serial number not allowed")

        # Validate IP address
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError as e:
            raise ValueError(f"Invalid IP address format: {e}")

        # Check for localhost
        if addr.is_loopback:
            raise ValueError("Localhost IP address not allowed")

        # Check for unspecified (0.0.0.0)
        if addr.is_unspecified:
            raise ValueError("Unspecified IP address (0.0.0.0) not allowed")

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
            raise ValueError("Only IPv4 addresses are supported")

        # Validate port
        if not (1 <= port <= 65535):
            raise ValueError(f"Port must be between 1 and 65535, got {port}")

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

        # Validate cache TTL
        if cache_ttl is None:
            cache_ttl = self.DEFAULT_CACHE_TTL

        if not (self.MIN_CACHE_TTL <= cache_ttl <= self.MAX_CACHE_TTL):
            raise ValueError(
                f"cache_ttl must be between {self.MIN_CACHE_TTL} "
                f"and {self.MAX_CACHE_TTL}, got {cache_ttl}"
            )

        # Store normalized serial as 12-digit hex string
        self.serial = serial_obj.to_string()
        self.ip = ip
        self.port = port
        self.cache_ttl = cache_ttl

        # Create lightweight connection handle - connection pooling is internal
        self.connection = DeviceConnection(
            serial=self.serial,
            ip=self.ip,
            port=self.port,
            timeout=timeout,
            max_retries=max_retries,
        )

        # State cache: key -> (value, timestamp, ttl)
        self._cache: dict[str, tuple[Any, float, float]] = {}

        # Product capabilities for device features (populated on first use)
        self._capabilities: ProductInfo | None = None

    @classmethod
    async def from_ip(
        cls,
        ip: str,
        port: int = LIFX_UDP_PORT,
        serial: str | None = None,
        timeout: float = 1.0,
    ) -> Self:
        """Create and return an instance for the given IP address.

        This is a convenience class method for connecting to a known device
        by IP address. The returned instance can be used as a context manager.

        Args:
            ip: IP address of the device
            port: Port number (default LIFX_UDP_PORT)
            serial: Serial number as 12-digit hex string
            timeout: Request timeout for this light instance

        Returns:
            Device instance ready to use with async context manager

        Example:
            ```python
            async with Device.from_ip(ip="192.168.1.100") as device:
                label = await device.get_label()
            ```
        """
        if serial is None:
            temp_conn = DeviceConnection(serial="000000000000", ip=ip, port=port)
            response = await temp_conn.request(packets.Device.GetService(), timeout=2.0)
            if response and isinstance(response, packets.Device.StateService):
                if temp_conn.serial and temp_conn.serial != "000000000000":
                    return cls(
                        serial=temp_conn.serial, ip=ip, port=port, timeout=timeout
                    )
        else:
            return cls(serial=serial, ip=ip, port=port, timeout=timeout)

        raise LifxDeviceNotFoundError()

    async def __aenter__(self) -> Self:
        """Enter async context manager."""
        # No connection setup needed - connection pool handles everything
        # Populate product capabilities for device features
        await self._ensure_capabilities()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Exit async context manager."""
        # No connection cleanup needed - connection pool manages lifecycle
        pass

    def _get_cached(self, key: str) -> Any | None:
        """Get cached value if not expired.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found or expired
        """
        if key not in self._cache:
            return None

        value, timestamp, ttl = self._cache[key]
        # Permanent cache (inf TTL) never expires
        if ttl != float("inf") and time.time() - timestamp > ttl:
            # Expired
            del self._cache[key]
            return None

        return value

    def _set_cached(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Set cached value with current timestamp and TTL.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds
        """
        if ttl is None:
            # Use appropriate default TTL based on key type
            # State keys (short TTL): color, power, effects, zone/tile colors
            if (
                key
                in (
                    "color",
                    "power",
                    "tile_effect",
                    "multizone_effect",
                )
                or key.startswith("zones_")
                or key.startswith("tile_colors_")
            ):
                ttl = self.STATE_CACHE_TTL
            else:
                # Metadata keys (long TTL): label, version, info, etc.
                ttl = self.METADATA_CACHE_TTL
        self._cache[key] = (value, time.time(), ttl)

    def _invalidate_cache(self, key: str | None = None) -> None:
        """Invalidate cache entry or entire cache.

        Args:
            key: Cache key to invalidate (None to clear all)
        """
        if key is None:
            self._cache.clear()
        elif key in self._cache:
            del self._cache[key]

    async def _ensure_capabilities(self) -> None:
        """Ensure device capabilities are populated.

        This fetches the device version and firmware to determine product capabilities.
        If the device claims extended_multizone support but firmware is too old,
        the capability is removed.

        Called automatically when entering context manager, but can be called manually.
        """
        if self._capabilities is not None:
            return

        # Get device version to determine product ID
        version = await self.get_version(use_cache=True)
        self._capabilities = get_product(version.product)

        # If device has extended_multizone with minimum firmware requirement, verify it
        if self._capabilities and self._capabilities.has_extended_multizone:
            if self._capabilities.min_ext_mz_firmware is not None:
                firmware = await self.get_host_firmware(use_cache=True)
                firmware_version = (
                    firmware.version_major << 16
                ) | firmware.version_minor

                # If firmware is too old, remove the extended_multizone capability
                if firmware_version < self._capabilities.min_ext_mz_firmware:
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

    async def get_label(self, use_cache: bool = True) -> str:
        """Get device label/name.

        Args:
            use_cache: Use cached value if available (default True)

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
            ```
        """
        if use_cache:
            cached = self._get_cached("label")
            if cached is not None:
                return cached

        # Request automatically unpacks and decodes label
        state = await self.connection.request(packets.Device.GetLabel())

        # Label is already decoded to string by connection layer
        self._set_cached("label", state.label)
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

        # Update cache
        self._set_cached("label", label)
        _LOGGER.debug(
            {
                "class": "Device",
                "method": "set_label",
                "action": "change",
                "values": {"label": label},
            }
        )

    async def get_power(self, use_cache: bool = True) -> bool:
        """Get device power state.

        Args:
            use_cache: Use cached value if available (default True)

        Returns:
            True if device is powered on, False otherwise

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            LifxProtocolError: If response is invalid

        Example:
            ```python
            is_on = await device.get_power()
            print(f"Power: {'ON' if is_on else 'OFF'}")
            ```
        """
        if use_cache:
            cached = self._get_cached("power")
            if cached is not None:
                return cached

        # Request automatically unpacks response
        state = await self.connection.request(packets.Device.GetPower())

        # Power level is uint16 (0 or 65535)
        is_on = state.level > 0

        self._set_cached("power", is_on)
        _LOGGER.debug(
            {
                "class": "Device",
                "method": "get_power",
                "action": "query",
                "reply": {"level": state.level},
            }
        )
        return is_on

    async def set_power(self, on: bool) -> None:
        """Set device power state.

        Args:
            on: True to turn on, False to turn off

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond

        Example:
            ```python
            # Turn on
            await device.set_power(True)
            ```
        """
        # Power level: 0 for off, 65535 for on
        level = 65535 if on else 0

        # Request automatically handles acknowledgement
        await self.connection.request(
            packets.Device.SetPower(level=level),
        )

        # Update cache
        self._set_cached("power", on)
        _LOGGER.debug(
            {
                "class": "Device",
                "method": "set_power",
                "action": "change",
                "values": {"level": level},
            }
        )

    async def get_version(self, use_cache: bool = True) -> DeviceVersion:
        """Get device version information.

        Args:
            use_cache: Use cached value if available (default True)

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
        if use_cache:
            cached = self._get_cached("version")
            if cached is not None:
                return cached

        # Request automatically unpacks response
        state = await self.connection.request(packets.Device.GetVersion())

        version = DeviceVersion(
            vendor=state.vendor,
            product=state.product,
        )

        # Version is immutable - cache permanently
        self._set_cached("version", version, ttl=self.PERMANENT_CACHE_TTL)

        _LOGGER.debug(
            {
                "class": "Device",
                "method": "get_version",
                "action": "query",
                "reply": {"vendor": state.vendor, "product": state.product},
            }
        )
        return version

    async def get_info(self, use_cache: bool = True) -> DeviceInfo:
        """Get device runtime information.

        Args:
            use_cache: Use cached value if available (default True)

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
        if use_cache:
            cached = self._get_cached("info")
            if cached is not None:
                return cached

        # Request automatically unpacks response
        state = await self.connection.request(packets.Device.GetInfo())  # type: ignore

        info = DeviceInfo(time=state.time, uptime=state.uptime, downtime=state.downtime)

        self._set_cached("info", info)

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

    async def get_wifi_info(self, use_cache: bool = True) -> WifiInfo:
        """Get device WiFi module information.

        Args:
            use_cache: Use cached value if available (default True)

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
        if use_cache:
            cached = self._get_cached("wifi_info")
            if cached is not None:
                return cached

        # Request WiFi info from device
        state = await self.connection.request(packets.Device.GetWifiInfo())

        # Extract WiFi info from response
        wifi_info = WifiInfo(signal=state.signal, tx=state.tx, rx=state.rx)

        self._set_cached("wifi_info", wifi_info)

        _LOGGER.debug(
            {
                "class": "Device",
                "method": "get_wifi_info",
                "action": "query",
                "reply": {"signal": state.signal, "tx": state.tx, "rx": state.rx},
            }
        )
        return wifi_info

    async def get_host_firmware(self, use_cache: bool = True) -> FirmwareInfo:
        """Get device host (WiFi module) firmware information.

        Args:
            use_cache: Use cached value if available (default True)

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
        if use_cache:
            cached = self._get_cached("host_firmware")
            if cached is not None:
                return cached

        # Request automatically unpacks response
        state = await self.connection.request(packets.Device.GetHostFirmware())  # type: ignore

        firmware = FirmwareInfo(
            build=state.build,
            version_major=state.version_major,
            version_minor=state.version_minor,
        )

        # Host firmware is immutable - cache permanently
        self._set_cached("host_firmware", firmware, ttl=self.PERMANENT_CACHE_TTL)

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

    async def get_wifi_firmware(self, use_cache: bool = True) -> FirmwareInfo:
        """Get device WiFi module firmware information.

        Args:
            use_cache: Use cached value if available (default True)

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
        if use_cache:
            cached = self._get_cached("wifi_firmware")
            if cached is not None:
                return cached

        # Request automatically unpacks response
        state = await self.connection.request(packets.Device.GetWifiFirmware())  # type: ignore

        firmware = FirmwareInfo(
            build=state.build,
            version_major=state.version_major,
            version_minor=state.version_minor,
        )

        # WiFi firmware is immutable - cache permanently
        self._set_cached("wifi_firmware", firmware, ttl=self.PERMANENT_CACHE_TTL)

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

    async def get_location(self, use_cache: bool = True) -> LocationInfo:
        """Get device location information.

        Args:
            use_cache: Use cached value if available (default True)

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
        if use_cache:
            cached = self._get_cached("location")
            if cached is not None:
                return cached

        # Request automatically unpacks response
        state = await self.connection.request(packets.Device.GetLocation())  # type: ignore

        location = LocationInfo(
            location=state.location,
            label=state.label,
            updated_at=state.updated_at,
        )

        self._set_cached("location", location, ttl=self.METADATA_CACHE_TTL)

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

    async def set_location(self, label: str, *, discover_timeout: float = 3.0) -> None:
        """Set device location information.

        Automatically discovers devices on the network to check if any device already
        has the target location label. If found, reuses that existing UUID to ensure
        devices with the same label share the same location UUID. If not found,
        generates a new UUID for this label.

        Args:
            label: Location label (max 32 characters)
            discover_timeout: Timeout for device discovery in seconds (default 3.0)

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            ValueError: If label is invalid

        Example:
            ```python
            # Set device location - checks network for existing "Living Room" location
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
            discovered = await discover_devices(timeout=discover_timeout)

            # Check each device for the target label
            for disc in discovered:
                try:
                    # Create connection handle - no explicit open/close needed
                    temp_conn = DeviceConnection(
                        serial=disc.serial, ip=disc.ip, port=disc.port
                    )

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

        # Update cache
        location_info = LocationInfo(
            location=location_uuid_to_use, label=label, updated_at=updated_at
        )
        self._set_cached("location", location_info, ttl=self.METADATA_CACHE_TTL)
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

    async def get_group(self, use_cache: bool = True) -> GroupInfo:
        """Get device group information.

        Args:
            use_cache: Use cached value if available (default True)

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
        if use_cache:
            cached = self._get_cached("group")
            if cached is not None:
                return cached

        # Request automatically unpacks response
        state = await self.connection.request(packets.Device.GetGroup())  # type: ignore

        group = GroupInfo(
            group=state.group,
            label=state.label,
            updated_at=state.updated_at,
        )

        self._set_cached("group", group, ttl=self.METADATA_CACHE_TTL)

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

    async def set_group(self, label: str, *, discover_timeout: float = 3.0) -> None:
        """Set device group information.

        Automatically discovers devices on the network to check if any device already
        has the target group label. If found, reuses that existing UUID to ensure
        devices with the same label share the same group UUID. If not found,
        generates a new UUID for this label.

        Args:
            label: Group label (max 32 characters)
            discover_timeout: Timeout for device discovery in seconds (default 3.0)

        Raises:
            LifxDeviceNotFoundError: If device is not connected
            LifxTimeoutError: If device does not respond
            ValueError: If label is invalid

        Example:
            ```python
            # Set device group - checks network for existing "Bedroom Lights" group
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
            discovered = await discover_devices(timeout=discover_timeout)

            # Check each device for the target label
            for disc in discovered:
                try:
                    # Create connection handle - no explicit open/close needed
                    temp_conn = DeviceConnection(
                        serial=disc.serial, ip=disc.ip, port=disc.port
                    )

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

        # Update cache
        group_info = GroupInfo(
            group=group_uuid_to_use, label=label, updated_at=updated_at
        )
        self._set_cached("group", group_info, ttl=self.METADATA_CACHE_TTL)
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
    def location(self) -> LocationInfo | None:
        """Get cached location info if available.

        Use get_location() to fetch from device.

        Returns:
            Cached location info or None if not cached.
        """
        return self._get_cached("location")

    @property
    def group(self) -> GroupInfo | None:
        """Get cached group info if available.

        Use get_group() to fetch from device.

        Returns:
            Cached group info or None if not cached.
        """
        return self._get_cached("group")

    @property
    def model(self) -> str | None:
        """Get LIFX friendly model name if available.

        Returns:
            Model string from product registry.
        """
        if self.capabilities is not None:
            return self.capabilities.name

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

    def __repr__(self) -> str:
        """String representation of device."""
        return f"Device(serial={self.serial}, ip={self.ip}, port={self.port})"
