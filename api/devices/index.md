# Device Classes

Device classes provide direct control over LIFX devices. All device classes support async context managers for automatic resource cleanup.

## Base Device

The `Device` class provides common operations available on all LIFX devices.

### Device

```python
Device(
    serial: str,
    ip: str,
    port: int = LIFX_UDP_PORT,
    timeout: float = DEFAULT_REQUEST_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
)
```

Base class for LIFX devices.

This class provides common functionality for all LIFX devices:

- Connection management
- Basic device queries (label, power, version, info)
- State caching for reduced network traffic

Properties return cached values or None if never fetched. Use get\_\*() methods to fetch fresh data from the device.

Example

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

| PARAMETER     | DESCRIPTION                                                                                              |
| ------------- | -------------------------------------------------------------------------------------------------------- |
| `serial`      | Device serial number as 12-digit hex string (e.g., "d073d5123456") **TYPE:** `str`                       |
| `ip`          | Device IP address **TYPE:** `str`                                                                        |
| `port`        | Device UDP port **TYPE:** `int` **DEFAULT:** `LIFX_UDP_PORT`                                             |
| `timeout`     | Overall timeout for network requests in seconds **TYPE:** `float` **DEFAULT:** `DEFAULT_REQUEST_TIMEOUT` |
| `max_retries` | Maximum number of retry attempts for network requests **TYPE:** `int` **DEFAULT:** `DEFAULT_MAX_RETRIES` |

| RAISES       | DESCRIPTION                 |
| ------------ | --------------------------- |
| `ValueError` | If any parameter is invalid |

| METHOD              | DESCRIPTION                                             |
| ------------------- | ------------------------------------------------------- |
| `from_ip`           | Create and return an instance for the given IP address. |
| `get_label`         | Get device label/name.                                  |
| `set_label`         | Set device label/name.                                  |
| `get_power`         | Get device power state.                                 |
| `set_power`         | Set device power state.                                 |
| `get_version`       | Get device version information.                         |
| `get_info`          | Get device runtime information.                         |
| `get_wifi_info`     | Get device WiFi module information.                     |
| `get_host_firmware` | Get device host (WiFi module) firmware information.     |
| `get_wifi_firmware` | Get device WiFi module firmware information.            |
| `get_location`      | Get device location information.                        |
| `set_location`      | Set device location information.                        |
| `get_group`         | Get device group information.                           |
| `set_group`         | Set device group information.                           |
| `set_reboot`        | Reboot the device.                                      |

| ATTRIBUTE       | DESCRIPTION                                                     |
| --------------- | --------------------------------------------------------------- |
| `capabilities`  | Get device product capabilities. **TYPE:** \`ProductInfo        |
| `label`         | Get cached label if available. **TYPE:** \`str                  |
| `version`       | Get cached version if available. **TYPE:** \`DeviceVersion      |
| `host_firmware` | Get cached host firmware if available. **TYPE:** \`FirmwareInfo |
| `wifi_firmware` | Get cached wifi firmware if available. **TYPE:** \`FirmwareInfo |
| `location`      | Get cached location name if available. **TYPE:** \`str          |
| `group`         | Get cached group name if available. **TYPE:** \`str             |
| `model`         | Get LIFX friendly model name if available. **TYPE:** \`str      |
| `mac_address`   | Get cached MAC address if available. **TYPE:** \`str            |

Source code in `src/lifx/devices/base.py`

```python
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
        raise ValueError("Localhost IP address not allowed")  # pragma: no cover

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
```

#### Attributes

##### capabilities

```python
capabilities: ProductInfo | None
```

Get device product capabilities.

Returns product information including supported features like:

- color, infrared, multizone, extended_multizone
- matrix (for tiles), chain, relays, buttons, hev
- temperature_range

Capabilities are automatically loaded when using device as context manager.

| RETURNS       | DESCRIPTION |
| ------------- | ----------- |
| \`ProductInfo | None\`      |

Example

```python
async with device:
    if device.capabilities and device.capabilities.has_multizone:
        print("Device supports multizone")
    if device.capabilities and device.capabilities.has_extended_multizone:
        print("Device supports extended multizone")
```

##### label

```python
label: str | None
```

Get cached label if available.

Use get_label() to fetch from device.

| RETURNS | DESCRIPTION |
| ------- | ----------- |
| \`str   | None\`      |

##### version

```python
version: DeviceVersion | None
```

Get cached version if available.

Use get_version() to fetch from device.

| RETURNS         | DESCRIPTION |
| --------------- | ----------- |
| \`DeviceVersion | None\`      |

##### host_firmware

```python
host_firmware: FirmwareInfo | None
```

Get cached host firmware if available.

Use get_host_firmware() to fetch from device.

| RETURNS        | DESCRIPTION |
| -------------- | ----------- |
| \`FirmwareInfo | None\`      |

##### wifi_firmware

```python
wifi_firmware: FirmwareInfo | None
```

Get cached wifi firmware if available.

Use get_wifi_firmware() to fetch from device.

| RETURNS        | DESCRIPTION |
| -------------- | ----------- |
| \`FirmwareInfo | None\`      |

##### location

```python
location: str | None
```

Get cached location name if available.

Use get_location() to fetch from device.

| RETURNS | DESCRIPTION |
| ------- | ----------- |
| \`str   | None\`      |

##### group

```python
group: str | None
```

Get cached group name if available.

Use get_group() to fetch from device.

| RETURNS | DESCRIPTION |
| ------- | ----------- |
| \`str   | None\`      |

##### model

```python
model: str | None
```

Get LIFX friendly model name if available.

| RETURNS | DESCRIPTION |
| ------- | ----------- |
| \`str   | None\`      |

##### mac_address

```python
mac_address: str | None
```

Get cached MAC address if available.

Use get_host_firmware() to calculate MAC address from device firmware.

| RETURNS | DESCRIPTION |
| ------- | ----------- |
| \`str   | None\`      |
| \`str   | None\`      |

#### Functions

##### from_ip

```python
from_ip(
    ip: str,
    port: int = LIFX_UDP_PORT,
    serial: str | None = None,
    timeout: float = DEFAULT_REQUEST_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> Self
```

Create and return an instance for the given IP address.

This is a convenience class method for connecting to a known device by IP address. The returned instance can be used as a context manager.

| PARAMETER | DESCRIPTION                                                                                       |
| --------- | ------------------------------------------------------------------------------------------------- |
| `ip`      | IP address of the device **TYPE:** `str`                                                          |
| `port`    | Port number (default LIFX_UDP_PORT) **TYPE:** `int` **DEFAULT:** `LIFX_UDP_PORT`                  |
| `serial`  | Serial number as 12-digit hex string **TYPE:** \`str                                              |
| `timeout` | Request timeout for this device instance **TYPE:** `float` **DEFAULT:** `DEFAULT_REQUEST_TIMEOUT` |

| RETURNS | DESCRIPTION                                             |
| ------- | ------------------------------------------------------- |
| `Self`  | Device instance ready to use with async context manager |

Example

```python
async with await Device.from_ip(ip="192.168.1.100") as device:
    label = await device.get_label()
```

Source code in `src/lifx/devices/base.py`

````python
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
    else:
        return cls(
            serial=serial,
            ip=ip,
            port=port,
            timeout=timeout,
            max_retries=max_retries,
        )

    raise LifxDeviceNotFoundError()
````

##### get_label

```python
get_label() -> str
```

Get device label/name.

Always fetches from device. Use the `label` property to access stored value.

| RETURNS | DESCRIPTION                                 |
| ------- | ------------------------------------------- |
| `str`   | Device label as string (max 32 bytes UTF-8) |

| RAISES                    | DESCRIPTION                |
| ------------------------- | -------------------------- |
| `LifxDeviceNotFoundError` | If device is not connected |
| `LifxTimeoutError`        | If device does not respond |
| `LifxProtocolError`       | If response is invalid     |

Example

```python
label = await device.get_label()
print(f"Device name: {label}")

# Or use cached value
if device.label:
    print(f"Cached label: {device.label}")
```

Source code in `src/lifx/devices/base.py`

````python
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
````

##### set_label

```python
set_label(label: str) -> None
```

Set device label/name.

| PARAMETER | DESCRIPTION                                           |
| --------- | ----------------------------------------------------- |
| `label`   | New device label (max 32 bytes UTF-8) **TYPE:** `str` |

| RAISES                    | DESCRIPTION                |
| ------------------------- | -------------------------- |
| `ValueError`              | If label is too long       |
| `LifxDeviceNotFoundError` | If device is not connected |
| `LifxTimeoutError`        | If device does not respond |

Example

```python
# Set label
await device.set_label("Living Room Light")
```

Source code in `src/lifx/devices/base.py`

````python
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
````

##### get_power

```python
get_power() -> int
```

Get device power state.

Always fetches from device.

| RETURNS | DESCRIPTION                                      |
| ------- | ------------------------------------------------ |
| `int`   | Power level as integer (0 for off, 65535 for on) |

| RAISES                    | DESCRIPTION                |
| ------------------------- | -------------------------- |
| `LifxDeviceNotFoundError` | If device is not connected |
| `LifxTimeoutError`        | If device does not respond |
| `LifxProtocolError`       | If response is invalid     |

Example

```python
level = await device.get_power()
print(f"Power: {'ON' if level > 0 else 'OFF'}")
```

Source code in `src/lifx/devices/base.py`

````python
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
````

##### set_power

```python
set_power(level: bool | int) -> None
```

Set device power state.

| PARAMETER | DESCRIPTION                                                 |
| --------- | ----------------------------------------------------------- |
| `level`   | True/65535 to turn on, False/0 to turn off **TYPE:** \`bool |

| RAISES                    | DESCRIPTION                        |
| ------------------------- | ---------------------------------- |
| `ValueError`              | If integer value is not 0 or 65535 |
| `LifxDeviceNotFoundError` | If device is not connected         |
| `LifxTimeoutError`        | If device does not respond         |

Example

```python
# Turn on device with boolean
await device.set_power(True)

# Turn on device with integer
await device.set_power(65535)

# Turn off device
await device.set_power(False)
await device.set_power(0)
```

Source code in `src/lifx/devices/base.py`

````python
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
````

##### get_version

```python
get_version() -> DeviceVersion
```

Get device version information.

Always fetches from device.

| RETURNS         | DESCRIPTION                                  |
| --------------- | -------------------------------------------- |
| `DeviceVersion` | DeviceVersion with vendor and product fields |

| RAISES                    | DESCRIPTION                |
| ------------------------- | -------------------------- |
| `LifxDeviceNotFoundError` | If device is not connected |
| `LifxTimeoutError`        | If device does not respond |
| `LifxProtocolError`       | If response is invalid     |

Example

```python
version = await device.get_version()
print(f"Vendor: {version.vendor}, Product: {version.product}")
```

Source code in `src/lifx/devices/base.py`

````python
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
````

##### get_info

```python
get_info() -> DeviceInfo
```

Get device runtime information.

Always fetches from device.

| RETURNS      | DESCRIPTION                                |
| ------------ | ------------------------------------------ |
| `DeviceInfo` | DeviceInfo with time, uptime, and downtime |

| RAISES                    | DESCRIPTION                |
| ------------------------- | -------------------------- |
| `LifxDeviceNotFoundError` | If device is not connected |
| `LifxTimeoutError`        | If device does not respond |
| `LifxProtocolError`       | If response is invalid     |

Example

```python
info = await device.get_info()
uptime_hours = info.uptime / 1e9 / 3600
print(f"Uptime: {uptime_hours:.1f} hours")
```

Source code in `src/lifx/devices/base.py`

````python
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
````

##### get_wifi_info

```python
get_wifi_info() -> WifiInfo
```

Get device WiFi module information.

Always fetches from device.

| RETURNS    | DESCRIPTION                                     |
| ---------- | ----------------------------------------------- |
| `WifiInfo` | WifiInfo with signal strength and network stats |

| RAISES                    | DESCRIPTION                |
| ------------------------- | -------------------------- |
| `LifxDeviceNotFoundError` | If device is not connected |
| `LifxTimeoutError`        | If device does not respond |
| `LifxProtocolError`       | If response is invalid     |

Example

```python
wifi_info = await device.get_wifi_info()
print(f"WiFi signal: {wifi_info.signal} mW")
print(f"TX: {wifi_info.tx} bytes, RX: {wifi_info.rx} bytes")
```

Source code in `src/lifx/devices/base.py`

````python
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
````

##### get_host_firmware

```python
get_host_firmware() -> FirmwareInfo
```

Get device host (WiFi module) firmware information.

Always fetches from device.

| RETURNS        | DESCRIPTION                                   |
| -------------- | --------------------------------------------- |
| `FirmwareInfo` | FirmwareInfo with build timestamp and version |

| RAISES                    | DESCRIPTION                |
| ------------------------- | -------------------------- |
| `LifxDeviceNotFoundError` | If device is not connected |
| `LifxTimeoutError`        | If device does not respond |
| `LifxProtocolError`       | If response is invalid     |

Example

```python
firmware = await device.get_host_firmware()
print(f"Firmware: v{firmware.version_major}.{firmware.version_minor}")
```

Source code in `src/lifx/devices/base.py`

````python
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
````

##### get_wifi_firmware

```python
get_wifi_firmware() -> FirmwareInfo
```

Get device WiFi module firmware information.

Always fetches from device.

| RETURNS        | DESCRIPTION                                   |
| -------------- | --------------------------------------------- |
| `FirmwareInfo` | FirmwareInfo with build timestamp and version |

| RAISES                    | DESCRIPTION                |
| ------------------------- | -------------------------- |
| `LifxDeviceNotFoundError` | If device is not connected |
| `LifxTimeoutError`        | If device does not respond |
| `LifxProtocolError`       | If response is invalid     |

Example

```python
wifi_fw = await device.get_wifi_firmware()
print(f"WiFi Firmware: v{wifi_fw.version_major}.{wifi_fw.version_minor}")
```

Source code in `src/lifx/devices/base.py`

````python
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
````

##### get_location

```python
get_location() -> LocationInfo
```

Get device location information.

Always fetches from device.

| RETURNS        | DESCRIPTION                                                   |
| -------------- | ------------------------------------------------------------- |
| `LocationInfo` | LocationInfo with location UUID, label, and updated timestamp |

| RAISES                    | DESCRIPTION                |
| ------------------------- | -------------------------- |
| `LifxDeviceNotFoundError` | If device is not connected |
| `LifxTimeoutError`        | If device does not respond |
| `LifxProtocolError`       | If response is invalid     |

Example

```python
location = await device.get_location()
print(f"Location: {location.label}")
print(f"Location ID: {location.location.hex()}")
```

Source code in `src/lifx/devices/base.py`

````python
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
````

##### set_location

```python
set_location(
    label: str, *, discover_timeout: float = DISCOVERY_TIMEOUT
) -> None
```

Set device location information.

Automatically discovers devices on the network to check if any device already has the target location label. If found, reuses that existing UUID to ensure devices with the same label share the same location UUID. If not found, generates a new UUID for this label.

| PARAMETER          | DESCRIPTION                                                                                |
| ------------------ | ------------------------------------------------------------------------------------------ |
| `label`            | Location label (max 32 characters) **TYPE:** `str`                                         |
| `discover_timeout` | Timeout for device discovery in seconds **TYPE:** `float` **DEFAULT:** `DISCOVERY_TIMEOUT` |

| RAISES                    | DESCRIPTION                |
| ------------------------- | -------------------------- |
| `LifxDeviceNotFoundError` | If device is not connected |
| `LifxTimeoutError`        | If device does not respond |
| `ValueError`              | If label is invalid        |

Example

```python
# Set device location
await device.set_location("Living Room")

# If another device already has "Kitchen" location, this device will
# join that existing location UUID
await device.set_location("Kitchen")
```

Source code in `src/lifx/devices/base.py`

````python
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
````

##### get_group

```python
get_group() -> GroupInfo
```

Get device group information.

Always fetches from device.

| RETURNS     | DESCRIPTION                                             |
| ----------- | ------------------------------------------------------- |
| `GroupInfo` | GroupInfo with group UUID, label, and updated timestamp |

| RAISES                    | DESCRIPTION                |
| ------------------------- | -------------------------- |
| `LifxDeviceNotFoundError` | If device is not connected |
| `LifxTimeoutError`        | If device does not respond |
| `LifxProtocolError`       | If response is invalid     |

Example

```python
group = await device.get_group()
print(f"Group: {group.label}")
print(f"Group ID: {group.group.hex()}")
```

Source code in `src/lifx/devices/base.py`

````python
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
````

##### set_group

```python
set_group(label: str, *, discover_timeout: float = DISCOVERY_TIMEOUT) -> None
```

Set device group information.

Automatically discovers devices on the network to check if any device already has the target group label. If found, reuses that existing UUID to ensure devices with the same label share the same group UUID. If not found, generates a new UUID for this label.

| PARAMETER          | DESCRIPTION                                                                                |
| ------------------ | ------------------------------------------------------------------------------------------ |
| `label`            | Group label (max 32 characters) **TYPE:** `str`                                            |
| `discover_timeout` | Timeout for device discovery in seconds **TYPE:** `float` **DEFAULT:** `DISCOVERY_TIMEOUT` |

| RAISES                    | DESCRIPTION                |
| ------------------------- | -------------------------- |
| `LifxDeviceNotFoundError` | If device is not connected |
| `LifxTimeoutError`        | If device does not respond |
| `ValueError`              | If label is invalid        |

Example

```python
# Set device group
await device.set_group("Bedroom Lights")

# If another device already has "Upstairs" group, this device will
# join that existing group UUID
await device.set_group("Upstairs")
```

Source code in `src/lifx/devices/base.py`

````python
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
````

##### set_reboot

```python
set_reboot() -> None
```

Reboot the device.

This sends a reboot command to the device. The device will disconnect and restart. You should disconnect from the device after calling this method.

| RAISES                    | DESCRIPTION                |
| ------------------------- | -------------------------- |
| `LifxDeviceNotFoundError` | If device is not connected |
| `LifxTimeoutError`        | If device does not respond |

Example

```python
async with device:
    await device.set_reboot()
    # Device will reboot, connection will be lost
```

Note

After rebooting, you may need to wait 10-30 seconds before the device comes back online and is discoverable again.

Source code in `src/lifx/devices/base.py`

````python
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
````

## Light

The `Light` class provides color control and effects for standard LIFX lights.

### Light

```python
Light(*args, **kwargs)
```

Bases: `Device`

LIFX light device with color control.

Extends the base Device class with light-specific functionality:

- Color control (HSBK)
- Brightness control
- Color temperature control
- Waveform effects

Example

```python
light = Light(serial="d073d5123456", ip="192.168.1.100")

async with light:
    # Set color
    await light.set_color(HSBK.from_rgb(255, 0, 0))

    # Set brightness
    await light.set_brightness(0.5)

    # Set temperature
    await light.set_temperature(3500)
```

Using the simplified connect method (without knowing the serial):

```python
async with await Light.from_ip(ip="192.168.1.100") as light:
    await light.set_color(HSBK.from_rgb(255, 0, 0))
```

| METHOD                  | DESCRIPTION                                                             |
| ----------------------- | ----------------------------------------------------------------------- |
| `get_color`             | Get current light color, power, and label.                              |
| `set_color`             | Set light color.                                                        |
| `set_brightness`        | Set light brightness only, preserving hue, saturation, and temperature. |
| `set_kelvin`            | Set light color temperature, preserving brightness. Saturation is       |
| `set_hue`               | Set light hue only, preserving saturation, brightness, and temperature. |
| `set_saturation`        | Set light saturation only, preserving hue, brightness, and temperature. |
| `get_power`             | Get light power state (specific to light, not device).                  |
| `set_power`             | Set light power state (specific to light, not device).                  |
| `set_waveform`          | Apply a waveform effect to the light.                                   |
| `set_waveform_optional` | Apply a waveform effect with selective color component control.         |
| `pulse`                 | Pulse the light to a specific color.                                    |
| `breathe`               | Make the light breathe to a specific color.                             |
| `apply_theme`           | Apply a theme to this light.                                            |

| ATTRIBUTE    | DESCRIPTION                                                          |
| ------------ | -------------------------------------------------------------------- |
| `min_kelvin` | Get the minimum supported kelvin value if available. **TYPE:** \`int |
| `max_kelvin` | Get the maximum supported kelvin value if available. **TYPE:** \`int |

Source code in `src/lifx/devices/light.py`

```python
def __init__(self, *args, **kwargs) -> None:
    """Initialize Light with additional state attributes."""
    super().__init__(*args, **kwargs)
```

#### Attributes

##### min_kelvin

```python
min_kelvin: int | None
```

Get the minimum supported kelvin value if available.

| RETURNS | DESCRIPTION |
| ------- | ----------- |
| \`int   | None\`      |

##### max_kelvin

```python
max_kelvin: int | None
```

Get the maximum supported kelvin value if available.

| RETURNS | DESCRIPTION |
| ------- | ----------- |
| \`int   | None\`      |

#### Functions

##### get_color

```python
get_color() -> tuple[HSBK, int, str]
```

Get current light color, power, and label.

Always fetches from device. Use the `color` property to access stored value.

Returns a tuple containing:

- color: HSBK color
- power: Power level as integer (0 for off, 65535 for on)
- label: Device label/name

| RETURNS                 | DESCRIPTION                    |
| ----------------------- | ------------------------------ |
| `tuple[HSBK, int, str]` | Tuple of (color, power, label) |

| RAISES                    | DESCRIPTION                |
| ------------------------- | -------------------------- |
| `LifxDeviceNotFoundError` | If device is not connected |
| `LifxTimeoutError`        | If device does not respond |
| `LifxProtocolError`       | If response is invalid     |

Example

```python
color, power, label = await light.get_color()
print(f"{label}: Hue: {color.hue}°, Power: {'ON' if power > 0 else 'OFF'}")
```

Source code in `src/lifx/devices/light.py`

````python
async def get_color(self) -> tuple[HSBK, int, str]:
    """Get current light color, power, and label.

    Always fetches from device. Use the `color` property to access stored value.

    Returns a tuple containing:
    - color: HSBK color
    - power: Power level as integer (0 for off, 65535 for on)
    - label: Device label/name

    Returns:
        Tuple of (color, power, label)

    Raises:
        LifxDeviceNotFoundError: If device is not connected
        LifxTimeoutError: If device does not respond
        LifxProtocolError: If response is invalid

    Example:
        ```python
        color, power, label = await light.get_color()
        print(f"{label}: Hue: {color.hue}°, Power: {'ON' if power > 0 else 'OFF'}")
        ```
    """
    # Request automatically unpacks response and decodes labels
    state = await self.connection.request(packets.Light.GetColor())

    # Convert from protocol HSBK to user-friendly HSBK
    color = HSBK.from_protocol(state.color)
    power = state.power
    label = state.label

    # Store label from StateColor response
    self._label = label  # Already decoded to string

    _LOGGER.debug(
        {
            "class": "Device",
            "method": "get_color",
            "action": "query",
            "reply": {
                "hue": state.color.hue,
                "saturation": state.color.saturation,
                "brightness": state.color.brightness,
                "kelvin": state.color.kelvin,
                "power": state.power,
                "label": state.label,
            },
        }
    )

    return color, power, label
````

##### set_color

```python
set_color(color: HSBK, duration: float = 0.0) -> None
```

Set light color.

| PARAMETER  | DESCRIPTION                                                                       |
| ---------- | --------------------------------------------------------------------------------- |
| `color`    | HSBK color to set **TYPE:** `HSBK`                                                |
| `duration` | Transition duration in seconds (default 0.0) **TYPE:** `float` **DEFAULT:** `0.0` |

| RAISES                    | DESCRIPTION                |
| ------------------------- | -------------------------- |
| `LifxDeviceNotFoundError` | If device is not connected |
| `LifxTimeoutError`        | If device does not respond |

Example

```python
# Set to red instantly
await light.set_color(HSBK.from_rgb(255, 0, 0))

# Fade to blue over 2 seconds
await light.set_color(HSBK.from_rgb(0, 0, 255), duration=2.0)
```

Source code in `src/lifx/devices/light.py`

````python
async def set_color(
    self,
    color: HSBK,
    duration: float = 0.0,
) -> None:
    """Set light color.

    Args:
        color: HSBK color to set
        duration: Transition duration in seconds (default 0.0)

    Raises:
        LifxDeviceNotFoundError: If device is not connected
        LifxTimeoutError: If device does not respond

    Example:
        ```python
        # Set to red instantly
        await light.set_color(HSBK.from_rgb(255, 0, 0))

        # Fade to blue over 2 seconds
        await light.set_color(HSBK.from_rgb(0, 0, 255), duration=2.0)
        ```
    """
    # Convert to protocol HSBK
    protocol_color = color.to_protocol()

    # Convert duration to milliseconds
    duration_ms = int(duration * 1000)

    # Request automatically handles acknowledgement
    await self.connection.request(
        packets.Light.SetColor(
            color=protocol_color,
            duration=duration_ms,
        ),
    )

    _LOGGER.debug(
        {
            "class": "Device",
            "method": "set_color",
            "action": "change",
            "values": {
                "hue": protocol_color.hue,
                "saturation": protocol_color.saturation,
                "brightness": protocol_color.brightness,
                "kelvin": protocol_color.kelvin,
                "duration": duration_ms,
            },
        }
    )
````

##### set_brightness

```python
set_brightness(brightness: float, duration: float = 0.0) -> None
```

Set light brightness only, preserving hue, saturation, and temperature.

| PARAMETER    | DESCRIPTION                                                                       |
| ------------ | --------------------------------------------------------------------------------- |
| `brightness` | Brightness level (0.0-1.0) **TYPE:** `float`                                      |
| `duration`   | Transition duration in seconds (default 0.0) **TYPE:** `float` **DEFAULT:** `0.0` |

| RAISES                    | DESCRIPTION                   |
| ------------------------- | ----------------------------- |
| `ValueError`              | If brightness is out of range |
| `LifxDeviceNotFoundError` | If device is not connected    |
| `LifxTimeoutError`        | If device does not respond    |

Example

```python
# Set to 50% brightness
await light.set_brightness(0.5)

# Fade to full brightness over 1 second
await light.set_brightness(1.0, duration=1.0)
```

Source code in `src/lifx/devices/light.py`

````python
async def set_brightness(self, brightness: float, duration: float = 0.0) -> None:
    """Set light brightness only, preserving hue, saturation, and temperature.

    Args:
        brightness: Brightness level (0.0-1.0)
        duration: Transition duration in seconds (default 0.0)

    Raises:
        ValueError: If brightness is out of range
        LifxDeviceNotFoundError: If device is not connected
        LifxTimeoutError: If device does not respond

    Example:
        ```python
        # Set to 50% brightness
        await light.set_brightness(0.5)

        # Fade to full brightness over 1 second
        await light.set_brightness(1.0, duration=1.0)
        ```
    """
    if not (0.0 <= brightness <= 1.0):
        raise ValueError(
            f"Brightness must be between 0.0 and 1.0, got {brightness}"
        )

    # Use set_waveform_optional with HALF_SINE waveform to set brightness
    # without needing to query current color values. Convert duration to seconds.
    color = HSBK(hue=0, saturation=0, brightness=brightness, kelvin=3500)

    await self.set_waveform_optional(
        color=color,
        period=max(duration, 0.001),
        cycles=1,
        waveform=LightWaveform.HALF_SINE,
        transient=False,
        set_hue=False,
        set_saturation=False,
        set_brightness=True,
        set_kelvin=False,
    )
````

##### set_kelvin

```python
set_kelvin(kelvin: int, duration: float = 0.0) -> None
```

Set light color temperature, preserving brightness. Saturation is automatically set to 0 to switch the light to color temperature mode.

| PARAMETER  | DESCRIPTION                                                                       |
| ---------- | --------------------------------------------------------------------------------- |
| `kelvin`   | Color temperature in Kelvin (1500-9000) **TYPE:** `int`                           |
| `duration` | Transition duration in seconds (default 0.0) **TYPE:** `float` **DEFAULT:** `0.0` |

| RAISES                    | DESCRIPTION                |
| ------------------------- | -------------------------- |
| `ValueError`              | If kelvin is out of range  |
| `LifxDeviceNotFoundError` | If device is not connected |
| `LifxTimeoutError`        | If device does not respond |

Example

```python
# Set to warm white
await light.set_kelvin(2500)

# Fade to cool white over 2 seconds
await light.set_kelvin(6500, duration=2.0)
```

Source code in `src/lifx/devices/light.py`

````python
async def set_kelvin(self, kelvin: int, duration: float = 0.0) -> None:
    """Set light color temperature, preserving brightness. Saturation is
       automatically set to 0 to switch the light to color temperature mode.

    Args:
        kelvin: Color temperature in Kelvin (1500-9000)
        duration: Transition duration in seconds (default 0.0)

    Raises:
        ValueError: If kelvin is out of range
        LifxDeviceNotFoundError: If device is not connected
        LifxTimeoutError: If device does not respond

    Example:
        ```python
        # Set to warm white
        await light.set_kelvin(2500)

        # Fade to cool white over 2 seconds
        await light.set_kelvin(6500, duration=2.0)
        ```
    """
    if not (HSBK.MIN_KELVIN <= kelvin <= HSBK.MAX_KELVIN):
        raise ValueError(f"Kelvin must be 1500-9000, got {kelvin}")

    # Use set_waveform_optional with HALF_SINE waveform to set kelvin
    # and saturation without needing to query current color values
    color = HSBK(hue=0, saturation=0, brightness=1.0, kelvin=kelvin)

    await self.set_waveform_optional(
        color=color,
        period=max(duration, 0.001),
        cycles=1,
        waveform=LightWaveform.HALF_SINE,
        transient=False,
        set_hue=False,
        set_saturation=True,
        set_brightness=False,
        set_kelvin=True,
    )
````

##### set_hue

```python
set_hue(hue: float, duration: float = 0.0) -> None
```

Set light hue only, preserving saturation, brightness, and temperature.

| PARAMETER  | DESCRIPTION                                                                       |
| ---------- | --------------------------------------------------------------------------------- |
| `hue`      | Hue in degrees (0-360) **TYPE:** `float`                                          |
| `duration` | Transition duration in seconds (default 0.0) **TYPE:** `float` **DEFAULT:** `0.0` |

| RAISES                    | DESCRIPTION                |
| ------------------------- | -------------------------- |
| `ValueError`              | If hue is out of range     |
| `LifxDeviceNotFoundError` | If device is not connected |
| `LifxTimeoutError`        | If device does not respond |

Example

```python
# Set to red (0 degrees)
await light.set_hue(0)

# Cycle through rainbow
for hue in range(0, 360, 10):
    await light.set_hue(hue, duration=0.5)
```

Source code in `src/lifx/devices/light.py`

````python
async def set_hue(self, hue: float, duration: float = 0.0) -> None:
    """Set light hue only, preserving saturation, brightness, and temperature.

    Args:
        hue: Hue in degrees (0-360)
        duration: Transition duration in seconds (default 0.0)

    Raises:
        ValueError: If hue is out of range
        LifxDeviceNotFoundError: If device is not connected
        LifxTimeoutError: If device does not respond

    Example:
        ```python
        # Set to red (0 degrees)
        await light.set_hue(0)

        # Cycle through rainbow
        for hue in range(0, 360, 10):
            await light.set_hue(hue, duration=0.5)
        ```
    """
    if not (HSBK.MIN_HUE <= hue <= HSBK.MAX_HUE):
        raise ValueError(
            f"Hue must be between {HSBK.MIN_HUE} and {HSBK.MAX_HUE}, got {hue}"
        )

    # Use set_waveform_optional with HALF_SINE waveform to set hue
    # without needing to query current color values
    color = HSBK(hue=hue, saturation=1.0, brightness=1.0, kelvin=3500)

    await self.set_waveform_optional(
        color=color,
        period=max(duration, 0.001),
        cycles=1,
        waveform=LightWaveform.HALF_SINE,
        transient=False,
        set_hue=True,
        set_saturation=False,
        set_brightness=False,
        set_kelvin=False,
    )
````

##### set_saturation

```python
set_saturation(saturation: float, duration: float = 0.0) -> None
```

Set light saturation only, preserving hue, brightness, and temperature.

| PARAMETER    | DESCRIPTION                                                                       |
| ------------ | --------------------------------------------------------------------------------- |
| `saturation` | Saturation level (0.0-1.0) **TYPE:** `float`                                      |
| `duration`   | Transition duration in seconds (default 0.0) **TYPE:** `float` **DEFAULT:** `0.0` |

| RAISES                    | DESCRIPTION                   |
| ------------------------- | ----------------------------- |
| `ValueError`              | If saturation is out of range |
| `LifxDeviceNotFoundError` | If device is not connected    |
| `LifxTimeoutError`        | If device does not respond    |

Example

```python
# Set to fully saturated
await light.set_saturation(1.0)

# Fade to white (no saturation) over 2 seconds
await light.set_saturation(0.0, duration=2.0)
```

Source code in `src/lifx/devices/light.py`

````python
async def set_saturation(self, saturation: float, duration: float = 0.0) -> None:
    """Set light saturation only, preserving hue, brightness, and temperature.

    Args:
        saturation: Saturation level (0.0-1.0)
        duration: Transition duration in seconds (default 0.0)

    Raises:
        ValueError: If saturation is out of range
        LifxDeviceNotFoundError: If device is not connected
        LifxTimeoutError: If device does not respond

    Example:
        ```python
        # Set to fully saturated
        await light.set_saturation(1.0)

        # Fade to white (no saturation) over 2 seconds
        await light.set_saturation(0.0, duration=2.0)
        ```
    """
    if not (HSBK.MIN_SATURATION <= saturation <= HSBK.MAX_SATURATION):
        raise ValueError(f"Saturation must be 0.0-1.0, got {saturation}")

    # Use set_waveform_optional with HALF_SINE waveform to set saturation
    # without needing to query current color values
    color = HSBK(hue=0, saturation=saturation, brightness=1.0, kelvin=3500)

    await self.set_waveform_optional(
        color=color,
        period=max(duration, 0.001),
        cycles=1,
        waveform=LightWaveform.HALF_SINE,
        transient=False,
        set_hue=False,
        set_saturation=True,
        set_brightness=False,
        set_kelvin=False,
    )
````

##### get_power

```python
get_power() -> int
```

Get light power state (specific to light, not device).

Always fetches from device.

This overrides Device.get_power() as it queries the light-specific power state (packet type 116/118) instead of device power (packet type 20/22).

| RETURNS | DESCRIPTION                                      |
| ------- | ------------------------------------------------ |
| `int`   | Power level as integer (0 for off, 65535 for on) |

| RAISES                    | DESCRIPTION                |
| ------------------------- | -------------------------- |
| `LifxDeviceNotFoundError` | If device is not connected |
| `LifxTimeoutError`        | If device does not respond |
| `LifxProtocolError`       | If response is invalid     |

Example

```python
level = await light.get_power()
print(f"Light power: {'ON' if level > 0 else 'OFF'}")
```

Source code in `src/lifx/devices/light.py`

````python
async def get_power(self) -> int:
    """Get light power state (specific to light, not device).

    Always fetches from device.

    This overrides Device.get_power() as it queries the light-specific
    power state (packet type 116/118) instead of device power (packet type 20/22).

    Returns:
        Power level as integer (0 for off, 65535 for on)

    Raises:
        LifxDeviceNotFoundError: If device is not connected
        LifxTimeoutError: If device does not respond
        LifxProtocolError: If response is invalid

    Example:
        ```python
        level = await light.get_power()
        print(f"Light power: {'ON' if level > 0 else 'OFF'}")
        ```
    """
    # Request automatically unpacks response
    state = await self.connection.request(packets.Light.GetPower())

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
````

##### set_power

```python
set_power(level: bool | int, duration: float = 0.0) -> None
```

Set light power state (specific to light, not device).

This overrides Device.set_power() as it uses the light-specific power packet (type 117) which supports transition duration.

| PARAMETER  | DESCRIPTION                                                                       |
| ---------- | --------------------------------------------------------------------------------- |
| `level`    | True/65535 to turn on, False/0 to turn off **TYPE:** \`bool                       |
| `duration` | Transition duration in seconds (default 0.0) **TYPE:** `float` **DEFAULT:** `0.0` |

| RAISES                    | DESCRIPTION                        |
| ------------------------- | ---------------------------------- |
| `ValueError`              | If integer value is not 0 or 65535 |
| `LifxDeviceNotFoundError` | If device is not connected         |
| `LifxTimeoutError`        | If device does not respond         |

Example

```python
# Turn on instantly with boolean
await light.set_power(True)

# Turn on with integer
await light.set_power(65535)

# Fade off over 3 seconds
await light.set_power(False, duration=3.0)
await light.set_power(0, duration=3.0)
```

Source code in `src/lifx/devices/light.py`

````python
async def set_power(self, level: bool | int, duration: float = 0.0) -> None:
    """Set light power state (specific to light, not device).

    This overrides Device.set_power() as it uses the light-specific
    power packet (type 117) which supports transition duration.

    Args:
        level: True/65535 to turn on, False/0 to turn off
        duration: Transition duration in seconds (default 0.0)

    Raises:
        ValueError: If integer value is not 0 or 65535
        LifxDeviceNotFoundError: If device is not connected
        LifxTimeoutError: If device does not respond

    Example:
        ```python
        # Turn on instantly with boolean
        await light.set_power(True)

        # Turn on with integer
        await light.set_power(65535)

        # Fade off over 3 seconds
        await light.set_power(False, duration=3.0)
        await light.set_power(0, duration=3.0)
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

    # Convert duration to milliseconds
    duration_ms = int(duration * 1000)

    # Request automatically handles acknowledgement
    await self.connection.request(
        packets.Light.SetPower(level=power_level, duration=duration_ms),
    )

    _LOGGER.debug(
        {
            "class": "Device",
            "method": "set_power",
            "action": "change",
            "values": {"level": power_level, "duration": duration_ms},
        }
    )
````

##### set_waveform

```python
set_waveform(
    color: HSBK,
    period: float,
    cycles: float,
    waveform: LightWaveform,
    transient: bool = True,
    skew_ratio: float = 0.5,
) -> None
```

Apply a waveform effect to the light.

Waveforms create repeating color transitions. Useful for effects like pulsing, breathing, or blinking.

| PARAMETER    | DESCRIPTION                                                                                        |
| ------------ | -------------------------------------------------------------------------------------------------- |
| `color`      | Target color for the waveform **TYPE:** `HSBK`                                                     |
| `period`     | Period of one cycle in seconds **TYPE:** `float`                                                   |
| `cycles`     | Number of cycles **TYPE:** `float`                                                                 |
| `waveform`   | Waveform type (SAW, SINE, HALF_SINE, TRIANGLE, PULSE) **TYPE:** `LightWaveform`                    |
| `transient`  | If True, return to original color after effect (default True) **TYPE:** `bool` **DEFAULT:** `True` |
| `skew_ratio` | Waveform skew (0.0-1.0, default 0.5 for symmetric) **TYPE:** `float` **DEFAULT:** `0.5`            |

| RAISES                    | DESCRIPTION                    |
| ------------------------- | ------------------------------ |
| `ValueError`              | If parameters are out of range |
| `LifxDeviceNotFoundError` | If device is not connected     |
| `LifxTimeoutError`        | If device does not respond     |

Example

```python
from lifx.protocol.protocol_types import LightWaveform

# Pulse red 5 times
await light.set_waveform(
    color=HSBK.from_rgb(255, 0, 0),
    period=1.0,
    cycles=5,
    waveform=LightWaveform.SINE,
)

# Breathe white once
await light.set_waveform(
    color=HSBK(0, 0, 1.0, 3500),
    period=2.0,
    cycles=1,
    waveform=LightWaveform.SINE,
    transient=False,
)
```

Source code in `src/lifx/devices/light.py`

````python
async def set_waveform(
    self,
    color: HSBK,
    period: float,
    cycles: float,
    waveform: LightWaveform,
    transient: bool = True,
    skew_ratio: float = 0.5,
) -> None:
    """Apply a waveform effect to the light.

    Waveforms create repeating color transitions. Useful for effects like
    pulsing, breathing, or blinking.

    Args:
        color: Target color for the waveform
        period: Period of one cycle in seconds
        cycles: Number of cycles
        waveform: Waveform type (SAW, SINE, HALF_SINE, TRIANGLE, PULSE)
        transient: If True, return to original color after effect (default True)
        skew_ratio: Waveform skew (0.0-1.0, default 0.5 for symmetric)

    Raises:
        ValueError: If parameters are out of range
        LifxDeviceNotFoundError: If device is not connected
        LifxTimeoutError: If device does not respond

    Example:
        ```python
        from lifx.protocol.protocol_types import LightWaveform

        # Pulse red 5 times
        await light.set_waveform(
            color=HSBK.from_rgb(255, 0, 0),
            period=1.0,
            cycles=5,
            waveform=LightWaveform.SINE,
        )

        # Breathe white once
        await light.set_waveform(
            color=HSBK(0, 0, 1.0, 3500),
            period=2.0,
            cycles=1,
            waveform=LightWaveform.SINE,
            transient=False,
        )
        ```
    """
    if period <= 0:
        raise ValueError(f"Period must be positive, got {period}")
    if cycles < 1:
        raise ValueError(f"Cycles must be 1 or higher, got {cycles}")
    if not (0.0 <= skew_ratio <= 1.0):
        raise ValueError(
            f"Skew ratio must be between 0.0 and 1.0, got {skew_ratio}"
        )

    # Convert to protocol values
    protocol_color = color.to_protocol()
    period_ms = int(period * 1000)
    skew_ratio_i16 = int(skew_ratio * 65535) - 32768  # Convert to int16 range

    # Send request
    await self.connection.request(
        packets.Light.SetWaveform(
            transient=bool(transient),
            color=protocol_color,
            period=period_ms,
            cycles=cycles,
            skew_ratio=skew_ratio_i16,
            waveform=waveform,
        ),
    )
    _LOGGER.debug(
        {
            "class": "Device",
            "method": "set_waveform",
            "action": "change",
            "values": {
                "transient": transient,
                "hue": protocol_color.hue,
                "saturation": protocol_color.saturation,
                "brightness": protocol_color.brightness,
                "kelvin": protocol_color.kelvin,
                "period": period_ms,
                "cycles": cycles,
                "skew_ratio": skew_ratio_i16,
                "waveform": waveform.value,
            },
        }
    )
````

##### set_waveform_optional

```python
set_waveform_optional(
    color: HSBK,
    period: float,
    cycles: float,
    waveform: LightWaveform,
    transient: bool = True,
    skew_ratio: float = 0.5,
    set_hue: bool = True,
    set_saturation: bool = True,
    set_brightness: bool = True,
    set_kelvin: bool = True,
) -> None
```

Apply a waveform effect with selective color component control.

Similar to set_waveform() but allows fine-grained control over which color components (hue, saturation, brightness, kelvin) are affected by the waveform. This enables effects like pulsing brightness while keeping hue constant, or cycling hue while maintaining brightness.

| PARAMETER        | DESCRIPTION                                                                                        |
| ---------------- | -------------------------------------------------------------------------------------------------- |
| `color`          | Target color for the waveform **TYPE:** `HSBK`                                                     |
| `period`         | Period of one cycle in seconds **TYPE:** `float`                                                   |
| `cycles`         | Number of cycles **TYPE:** `float`                                                                 |
| `waveform`       | Waveform type (SAW, SINE, HALF_SINE, TRIANGLE, PULSE) **TYPE:** `LightWaveform`                    |
| `transient`      | If True, return to original color after effect (default True) **TYPE:** `bool` **DEFAULT:** `True` |
| `skew_ratio`     | Waveform skew (0.0-1.0, default 0.5 for symmetric) **TYPE:** `float` **DEFAULT:** `0.5`            |
| `set_hue`        | Apply waveform to hue component (default True) **TYPE:** `bool` **DEFAULT:** `True`                |
| `set_saturation` | Apply waveform to saturation component (default True) **TYPE:** `bool` **DEFAULT:** `True`         |
| `set_brightness` | Apply waveform to brightness component (default True) **TYPE:** `bool` **DEFAULT:** `True`         |
| `set_kelvin`     | Apply waveform to kelvin component (default True) **TYPE:** `bool` **DEFAULT:** `True`             |

| RAISES                    | DESCRIPTION                    |
| ------------------------- | ------------------------------ |
| `ValueError`              | If parameters are out of range |
| `LifxDeviceNotFoundError` | If device is not connected     |
| `LifxTimeoutError`        | If device does not respond     |

Example

```python
from lifx.protocol.protocol_types import LightWaveform

# Pulse brightness only, keeping hue/saturation constant
await light.set_waveform_optional(
    color=HSBK(0, 1.0, 1.0, 3500),
    period=1.0,
    cycles=5,
    waveform=LightWaveform.SINE,
    set_hue=False,
    set_saturation=False,
    set_brightness=True,
    set_kelvin=False,
)

# Cycle hue while maintaining brightness
await light.set_waveform_optional(
    color=HSBK(180, 1.0, 1.0, 3500),
    period=5.0,
    cycles=0,  # Infinite
    waveform=LightWaveform.SAW,
    set_hue=True,
    set_saturation=False,
    set_brightness=False,
    set_kelvin=False,
)
```

Source code in `src/lifx/devices/light.py`

````python
async def set_waveform_optional(
    self,
    color: HSBK,
    period: float,
    cycles: float,
    waveform: LightWaveform,
    transient: bool = True,
    skew_ratio: float = 0.5,
    set_hue: bool = True,
    set_saturation: bool = True,
    set_brightness: bool = True,
    set_kelvin: bool = True,
) -> None:
    """Apply a waveform effect with selective color component control.

    Similar to set_waveform() but allows fine-grained control over which
    color components (hue, saturation, brightness, kelvin) are affected
    by the waveform. This enables effects like pulsing brightness while
    keeping hue constant, or cycling hue while maintaining brightness.

    Args:
        color: Target color for the waveform
        period: Period of one cycle in seconds
        cycles: Number of cycles
        waveform: Waveform type (SAW, SINE, HALF_SINE, TRIANGLE, PULSE)
        transient: If True, return to original color after effect (default True)
        skew_ratio: Waveform skew (0.0-1.0, default 0.5 for symmetric)
        set_hue: Apply waveform to hue component (default True)
        set_saturation: Apply waveform to saturation component (default True)
        set_brightness: Apply waveform to brightness component (default True)
        set_kelvin: Apply waveform to kelvin component (default True)

    Raises:
        ValueError: If parameters are out of range
        LifxDeviceNotFoundError: If device is not connected
        LifxTimeoutError: If device does not respond

    Example:
        ```python
        from lifx.protocol.protocol_types import LightWaveform

        # Pulse brightness only, keeping hue/saturation constant
        await light.set_waveform_optional(
            color=HSBK(0, 1.0, 1.0, 3500),
            period=1.0,
            cycles=5,
            waveform=LightWaveform.SINE,
            set_hue=False,
            set_saturation=False,
            set_brightness=True,
            set_kelvin=False,
        )

        # Cycle hue while maintaining brightness
        await light.set_waveform_optional(
            color=HSBK(180, 1.0, 1.0, 3500),
            period=5.0,
            cycles=0,  # Infinite
            waveform=LightWaveform.SAW,
            set_hue=True,
            set_saturation=False,
            set_brightness=False,
            set_kelvin=False,
        )
        ```
    """
    if period <= 0:
        raise ValueError(f"Period must be positive, got {period}")
    if cycles < 0:
        raise ValueError(f"Cycles must be non-negative, got {cycles}")
    if not (0.0 <= skew_ratio <= 1.0):
        raise ValueError(
            f"Skew ratio must be between 0.0 and 1.0, got {skew_ratio}"
        )

    # Convert to protocol values
    protocol_color = color.to_protocol()
    period_ms = int(period * 1000)
    skew_ratio_i16 = int(skew_ratio * 65535) - 32768  # Convert to int16 range

    # Send request
    await self.connection.request(
        packets.Light.SetWaveformOptional(
            transient=bool(transient),
            color=protocol_color,
            period=period_ms,
            cycles=cycles,
            skew_ratio=skew_ratio_i16,
            waveform=waveform,
            set_hue=set_hue,
            set_saturation=set_saturation,
            set_brightness=set_brightness,
            set_kelvin=set_kelvin,
        ),
    )
    _LOGGER.debug(
        {
            "class": "Device",
            "method": "set_waveform_optional",
            "action": "change",
            "values": {
                "transient": transient,
                "hue": protocol_color.hue,
                "saturation": protocol_color.saturation,
                "brightness": protocol_color.brightness,
                "kelvin": protocol_color.kelvin,
                "period": period_ms,
                "cycles": cycles,
                "skew_ratio": skew_ratio_i16,
                "waveform": waveform.value,
                "set_hue": set_hue,
                "set_saturation": set_saturation,
                "set_brightness": set_brightness,
                "set_kelvin": set_kelvin,
            },
        }
    )
````

##### pulse

```python
pulse(
    color: HSBK, period: float = 1.0, cycles: float = 1, transient: bool = True
) -> None
```

Pulse the light to a specific color.

Convenience method for creating a pulse effect using SINE waveform.

| PARAMETER   | DESCRIPTION                                                                                        |
| ----------- | -------------------------------------------------------------------------------------------------- |
| `color`     | Target color to pulse to **TYPE:** `HSBK`                                                          |
| `period`    | Period of one pulse in seconds (default 1.0) **TYPE:** `float` **DEFAULT:** `1.0`                  |
| `cycles`    | Number of pulses (default 1) **TYPE:** `float` **DEFAULT:** `1`                                    |
| `transient` | If True, return to original color after effect (default True) **TYPE:** `bool` **DEFAULT:** `True` |

Example

```python
# Pulse red once
await light.pulse(HSBK.from_rgb(255, 0, 0))

# Pulse blue 3 times, 2 seconds per pulse
await light.pulse(HSBK.from_rgb(0, 0, 255), period=2.0, cycles=3)
```

Source code in `src/lifx/devices/light.py`

````python
async def pulse(
    self,
    color: HSBK,
    period: float = 1.0,
    cycles: float = 1,
    transient: bool = True,
) -> None:
    """Pulse the light to a specific color.

    Convenience method for creating a pulse effect using SINE waveform.

    Args:
        color: Target color to pulse to
        period: Period of one pulse in seconds (default 1.0)
        cycles: Number of pulses (default 1)
        transient: If True, return to original color after effect (default True)

    Example:
        ```python
        # Pulse red once
        await light.pulse(HSBK.from_rgb(255, 0, 0))

        # Pulse blue 3 times, 2 seconds per pulse
        await light.pulse(HSBK.from_rgb(0, 0, 255), period=2.0, cycles=3)
        ```
    """
    await self.set_waveform(
        color=color,
        period=period,
        cycles=cycles,
        waveform=LightWaveform.PULSE,
        transient=transient,
    )
````

##### breathe

```python
breathe(color: HSBK, period: float = 2.0, cycles: float = 1) -> None
```

Make the light breathe to a specific color.

Convenience method for creating a breathing effect using SINE waveform.

| PARAMETER | DESCRIPTION                                                                        |
| --------- | ---------------------------------------------------------------------------------- |
| `color`   | Target color to breathe to **TYPE:** `HSBK`                                        |
| `period`  | Period of one breath in seconds (default 2.0) **TYPE:** `float` **DEFAULT:** `2.0` |
| `cycles`  | Number of breaths (default 1) **TYPE:** `float` **DEFAULT:** `1`                   |

Example

```python
# Breathe white once
await light.breathe(HSBK(0, 0, 1.0, 3500))

# Breathe purple 10 times
await light.breathe(HSBK.from_rgb(128, 0, 128), cycles=10)
```

Source code in `src/lifx/devices/light.py`

````python
async def breathe(
    self,
    color: HSBK,
    period: float = 2.0,
    cycles: float = 1,
) -> None:
    """Make the light breathe to a specific color.

    Convenience method for creating a breathing effect using SINE waveform.

    Args:
        color: Target color to breathe to
        period: Period of one breath in seconds (default 2.0)
        cycles: Number of breaths (default 1)

    Example:
        ```python
        # Breathe white once
        await light.breathe(HSBK(0, 0, 1.0, 3500))

        # Breathe purple 10 times
        await light.breathe(HSBK.from_rgb(128, 0, 128), cycles=10)
        ```
    """
    await self.set_waveform(
        color=color,
        period=period,
        cycles=cycles,
        waveform=LightWaveform.SINE,
        transient=True,
    )
````

##### apply_theme

```python
apply_theme(
    theme: Theme, power_on: bool = False, duration: float = 0.0
) -> None
```

Apply a theme to this light.

Selects a random color from the theme and applies it to the light.

| PARAMETER  | DESCRIPTION                                                         |
| ---------- | ------------------------------------------------------------------- |
| `theme`    | Theme to apply **TYPE:** `Theme`                                    |
| `power_on` | Turn on the light **TYPE:** `bool` **DEFAULT:** `False`             |
| `duration` | Transition duration in seconds **TYPE:** `float` **DEFAULT:** `0.0` |

Example

```python
from lifx.theme import get_theme

theme = get_theme("evening")
await light.apply_theme(theme, power_on=True, duration=0.5)
```

Source code in `src/lifx/devices/light.py`

````python
async def apply_theme(
    self,
    theme: Theme,
    power_on: bool = False,
    duration: float = 0.0,
) -> None:
    """Apply a theme to this light.

    Selects a random color from the theme and applies it to the light.

    Args:
        theme: Theme to apply
        power_on: Turn on the light
        duration: Transition duration in seconds

    Example:
        ```python
        from lifx.theme import get_theme

        theme = get_theme("evening")
        await light.apply_theme(theme, power_on=True, duration=0.5)
        ```
    """
    if self.capabilities is None:
        await self._ensure_capabilities()

    if self.capabilities and not self.capabilities.has_color:
        return

    # Select a random color from theme
    color = theme.random()

    # Check if light is on
    is_on = await self.get_power()

    # Apply color to light
    # If light is off and we're turning it on, set color immediately then fade on
    if power_on and not is_on:
        await self.set_color(color, duration=0)
        await self.set_power(True, duration=duration)
    else:
        # Light is already on, or we're not turning it on - apply with duration
        await self.set_color(color, duration=duration)
````

## HEV Light

The `HevLight` class extends `Light` with anti-bacterial cleaning cycle control for LIFX HEV devices.

### HevLight

```python
HevLight(*args, **kwargs)
```

Bases: `Light`

LIFX HEV light with anti-bacterial cleaning capabilities.

Extends the Light class with HEV (High Energy Visible) cycle control. HEV uses UV-C light to sanitize surfaces and air with anti-bacterial properties.

Example

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

| METHOD                | DESCRIPTION                                |
| --------------------- | ------------------------------------------ |
| `get_hev_cycle`       | Get current HEV cycle state.               |
| `set_hev_cycle`       | Start or stop a HEV cleaning cycle.        |
| `get_hev_config`      | Get HEV cycle configuration.               |
| `set_hev_config`      | Configure HEV cycle defaults.              |
| `get_last_hev_result` | Get result of the last HEV cleaning cycle. |

| ATTRIBUTE    | DESCRIPTION                                                                        |
| ------------ | ---------------------------------------------------------------------------------- |
| `hev_config` | Get cached HEV configuration if available. **TYPE:** \`HevConfig                   |
| `hev_result` | Get cached last HEV cycle result if available. **TYPE:** \`LightLastHevCycleResult |

Source code in `src/lifx/devices/hev.py`

```python
def __init__(self, *args, **kwargs) -> None:
    """Initialize HevLight with additional state attributes."""
    super().__init__(*args, **kwargs)
    # HEV-specific state storage
    self._hev_config: HevConfig | None = None
    self._hev_result: LightLastHevCycleResult | None = None
```

#### Attributes

##### hev_config

```python
hev_config: HevConfig | None
```

Get cached HEV configuration if available.

| RETURNS     | DESCRIPTION |
| ----------- | ----------- |
| \`HevConfig | None\`      |
| \`HevConfig | None\`      |

##### hev_result

```python
hev_result: LightLastHevCycleResult | None
```

Get cached last HEV cycle result if available.

| RETURNS                   | DESCRIPTION |
| ------------------------- | ----------- |
| \`LightLastHevCycleResult | None\`      |
| \`LightLastHevCycleResult | None\`      |

#### Functions

##### get_hev_cycle

```python
get_hev_cycle() -> HevCycleState
```

Get current HEV cycle state.

Always fetches from device. Use the `hev_cycle` property to access stored value.

| RETURNS         | DESCRIPTION                                                       |
| --------------- | ----------------------------------------------------------------- |
| `HevCycleState` | HevCycleState with duration, remaining time, and last power state |

| RAISES                    | DESCRIPTION                |
| ------------------------- | -------------------------- |
| `LifxDeviceNotFoundError` | If device is not connected |
| `LifxTimeoutError`        | If device does not respond |
| `LifxProtocolError`       | If response is invalid     |

Example

```python
state = await light.get_hev_cycle()
if state.is_running:
    print(f"HEV cleaning in progress: {state.remaining_s}s left")
else:
    print("No active cleaning cycle")
```

Source code in `src/lifx/devices/hev.py`

````python
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
````

##### set_hev_cycle

```python
set_hev_cycle(enable: bool, duration_seconds: int) -> None
```

Start or stop a HEV cleaning cycle.

| PARAMETER          | DESCRIPTION                                               |
| ------------------ | --------------------------------------------------------- |
| `enable`           | True to start cycle, False to stop **TYPE:** `bool`       |
| `duration_seconds` | Duration of the cleaning cycle in seconds **TYPE:** `int` |

| RAISES                    | DESCRIPTION                |
| ------------------------- | -------------------------- |
| `ValueError`              | If duration is negative    |
| `LifxDeviceNotFoundError` | If device is not connected |
| `LifxTimeoutError`        | If device does not respond |

Example

```python
# Start a 1-hour cleaning cycle
await light.set_hev_cycle(enable=True, duration_seconds=3600)

# Stop the current cycle
await light.set_hev_cycle(enable=False, duration_seconds=0)
```

Source code in `src/lifx/devices/hev.py`

````python
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
````

##### get_hev_config

```python
get_hev_config() -> HevConfig
```

Get HEV cycle configuration.

| RETURNS     | DESCRIPTION                                             |
| ----------- | ------------------------------------------------------- |
| `HevConfig` | HevConfig with indication and default duration settings |

| RAISES                    | DESCRIPTION                |
| ------------------------- | -------------------------- |
| `LifxDeviceNotFoundError` | If device is not connected |
| `LifxTimeoutError`        | If device does not respond |
| `LifxProtocolError`       | If response is invalid     |

Example

```python
config = await light.get_hev_config()
print(f"Default duration: {config.duration_s}s")
print(f"Visual indication: {config.indication}")
```

Source code in `src/lifx/devices/hev.py`

````python
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
````

##### set_hev_config

```python
set_hev_config(indication: bool, duration_seconds: int) -> None
```

Configure HEV cycle defaults.

| PARAMETER          | DESCRIPTION                                                        |
| ------------------ | ------------------------------------------------------------------ |
| `indication`       | Whether to show visual indication during cleaning **TYPE:** `bool` |
| `duration_seconds` | Default duration for cleaning cycles in seconds **TYPE:** `int`    |

| RAISES                    | DESCRIPTION                |
| ------------------------- | -------------------------- |
| `ValueError`              | If duration is negative    |
| `LifxDeviceNotFoundError` | If device is not connected |
| `LifxTimeoutError`        | If device does not respond |

Example

```python
# Configure 2-hour default with visual indication
await light.set_hev_config(indication=True, duration_seconds=7200)
```

Source code in `src/lifx/devices/hev.py`

````python
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
````

##### get_last_hev_result

```python
get_last_hev_result() -> LightLastHevCycleResult
```

Get result of the last HEV cleaning cycle.

| RETURNS                   | DESCRIPTION                                                                  |
| ------------------------- | ---------------------------------------------------------------------------- |
| `LightLastHevCycleResult` | LightLastHevCycleResult enum value indicating success or interruption reason |

| RAISES                    | DESCRIPTION                |
| ------------------------- | -------------------------- |
| `LifxDeviceNotFoundError` | If device is not connected |
| `LifxTimeoutError`        | If device does not respond |
| `LifxProtocolError`       | If response is invalid     |

Example

```python
result = await light.get_last_hev_result()
if result == LightLastHevCycleResult.SUCCESS:
    print("Last cleaning cycle completed successfully")
elif result == LightLastHevCycleResult.INTERRUPTED_BY_LAN:
    print("Cycle was interrupted by network command")
```

Source code in `src/lifx/devices/hev.py`

````python
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
````

## Infrared Light

The `InfraredLight` class extends `Light` with infrared LED control for night vision on LIFX A19 + Night Vision devices.

### InfraredLight

```python
InfraredLight(*args, **kwargs)
```

Bases: `Light`

LIFX infrared light with IR LED control.

Extends the Light class with infrared brightness control. Infrared LEDs automatically activate in low-light conditions to provide illumination for night vision cameras.

Example

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

| METHOD         | DESCRIPTION                      |
| -------------- | -------------------------------- |
| `get_infrared` | Get current infrared brightness. |
| `set_infrared` | Set infrared brightness.         |

| ATTRIBUTE  | DESCRIPTION                                                    |
| ---------- | -------------------------------------------------------------- |
| `infrared` | Get cached infrared brightness if available. **TYPE:** \`float |

Source code in `src/lifx/devices/infrared.py`

```python
def __init__(self, *args, **kwargs) -> None:
    """Initialize InfraredLight with additional state attributes."""
    super().__init__(*args, **kwargs)
    # Infrared-specific state storage
    self._infrared: float | None = None
```

#### Attributes

##### infrared

```python
infrared: float | None
```

Get cached infrared brightness if available.

| RETURNS | DESCRIPTION |
| ------- | ----------- |
| \`float | None\`      |
| \`float | None\`      |

#### Functions

##### get_infrared

```python
get_infrared() -> float
```

Get current infrared brightness.

| RETURNS | DESCRIPTION                   |
| ------- | ----------------------------- |
| `float` | Infrared brightness (0.0-1.0) |

| RAISES                    | DESCRIPTION                |
| ------------------------- | -------------------------- |
| `LifxDeviceNotFoundError` | If device is not connected |
| `LifxTimeoutError`        | If device does not respond |
| `LifxProtocolError`       | If response is invalid     |

Example

```python
brightness = await light.get_infrared()
if brightness > 0:
    print(f"IR LEDs active at {brightness * 100}%")
```

Source code in `src/lifx/devices/infrared.py`

````python
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
````

##### set_infrared

```python
set_infrared(brightness: float) -> None
```

Set infrared brightness.

| PARAMETER    | DESCRIPTION                                     |
| ------------ | ----------------------------------------------- |
| `brightness` | Infrared brightness (0.0-1.0) **TYPE:** `float` |

| RAISES                    | DESCRIPTION                   |
| ------------------------- | ----------------------------- |
| `ValueError`              | If brightness is out of range |
| `LifxDeviceNotFoundError` | If device is not connected    |
| `LifxTimeoutError`        | If device does not respond    |

Example

```python
# Set to 75% infrared brightness
await light.set_infrared(0.75)

# Turn off infrared
await light.set_infrared(0.0)
```

Source code in `src/lifx/devices/infrared.py`

````python
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
````

## MultiZone Light

The `MultiZoneLight` class controls LIFX strips and beams with multiple color zones.

### MultiZoneLight

```python
MultiZoneLight(*args, **kwargs)
```

Bases: `Light`

LIFX MultiZone light device (strips, beams).

Extends the Light class with zone-specific functionality:

- Individual zone color control
- Multi-zone effects (move, etc.)
- Extended color zone support for efficient bulk updates

Example

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

| METHOD                     | DESCRIPTION                                                          |
| -------------------------- | -------------------------------------------------------------------- |
| `get_zone_count`           | Get the number of zones in the device.                               |
| `get_color_zones`          | Get colors for a range of zones using GetColorZones.                 |
| `get_extended_color_zones` | Get colors for a range of zones using GetExtendedColorZones.         |
| `get_all_color_zones`      | Get colors for all zones, automatically using the best method.       |
| `set_color_zones`          | Set color for a range of zones.                                      |
| `set_extended_color_zones` | Set colors for multiple zones efficiently (up to 82 zones per call). |
| `get_multizone_effect`     | Get current multizone effect.                                        |
| `set_multizone_effect`     | Set multizone effect.                                                |
| `stop_effect`              | Stop any running multizone effect.                                   |
| `set_move_effect`          | Apply a moving effect that shifts colors along the strip.            |
| `apply_theme`              | Apply a theme across zones.                                          |

| ATTRIBUTE          | DESCRIPTION                                                           |
| ------------------ | --------------------------------------------------------------------- |
| `zone_count`       | Get cached zone count if available. **TYPE:** \`int                   |
| `multizone_effect` | Get cached multizone effect if available. **TYPE:** \`MultiZoneEffect |

Source code in `src/lifx/devices/multizone.py`

```python
def __init__(self, *args, **kwargs) -> None:
    """Initialize MultiZoneLight with additional state attributes."""
    super().__init__(*args, **kwargs)
    # MultiZone-specific state storage
    self._zone_count: int | None = None
    self._multizone_effect: MultiZoneEffect | None | None = None
```

#### Attributes

##### zone_count

```python
zone_count: int | None
```

Get cached zone count if available.

| RETURNS | DESCRIPTION |
| ------- | ----------- |
| \`int   | None\`      |
| \`int   | None\`      |

##### multizone_effect

```python
multizone_effect: MultiZoneEffect | None | None
```

Get cached multizone effect if available.

| RETURNS           | DESCRIPTION |
| ----------------- | ----------- |
| \`MultiZoneEffect | None        |
| \`MultiZoneEffect | None        |

#### Functions

##### get_zone_count

```python
get_zone_count() -> int
```

Get the number of zones in the device.

Always fetches from device. Use the `zone_count` property to access stored value.

| RETURNS | DESCRIPTION     |
| ------- | --------------- |
| `int`   | Number of zones |

| RAISES                    | DESCRIPTION                |
| ------------------------- | -------------------------- |
| `LifxDeviceNotFoundError` | If device is not connected |
| `LifxTimeoutError`        | If device does not respond |
| `LifxProtocolError`       | If response is invalid     |

Example

```python
zone_count = await light.get_zone_count()
print(f"Device has {zone_count} zones")
```

Source code in `src/lifx/devices/multizone.py`

````python
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
````

##### get_color_zones

```python
get_color_zones(start: int = 0, end: int = 255) -> list[HSBK]
```

Get colors for a range of zones using GetColorZones.

Always fetches from device. Use `zones` property to access stored values.

| PARAMETER | DESCRIPTION                                                                |
| --------- | -------------------------------------------------------------------------- |
| `start`   | Start zone index (inclusive, default 0) **TYPE:** `int` **DEFAULT:** `0`   |
| `end`     | End zone index (inclusive, default 255) **TYPE:** `int` **DEFAULT:** `255` |

| RETURNS      | DESCRIPTION                       |
| ------------ | --------------------------------- |
| `list[HSBK]` | List of HSBK colors, one per zone |

| RAISES                    | DESCRIPTION                 |
| ------------------------- | --------------------------- |
| `ValueError`              | If zone indices are invalid |
| `LifxDeviceNotFoundError` | If device is not connected  |
| `LifxTimeoutError`        | If device does not respond  |
| `LifxProtocolError`       | If response is invalid      |

Example

```python
# Get colors for all zones (default)
colors = await light.get_color_zones()

# Get colors for first 10 zones
colors = await light.get_color_zones(0, 9)
for i, color in enumerate(colors):
    print(f"Zone {i}: {color}")
```

Source code in `src/lifx/devices/multizone.py`

````python
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
````

##### get_extended_color_zones

```python
get_extended_color_zones(start: int = 0, end: int = 255) -> list[HSBK]
```

Get colors for a range of zones using GetExtendedColorZones.

Always fetches from device. Use `zones` property to access stored values.

| PARAMETER | DESCRIPTION                                                                |
| --------- | -------------------------------------------------------------------------- |
| `start`   | Start zone index (inclusive, default 0) **TYPE:** `int` **DEFAULT:** `0`   |
| `end`     | End zone index (inclusive, default 255) **TYPE:** `int` **DEFAULT:** `255` |

| RETURNS      | DESCRIPTION                       |
| ------------ | --------------------------------- |
| `list[HSBK]` | List of HSBK colors, one per zone |

| RAISES                    | DESCRIPTION                 |
| ------------------------- | --------------------------- |
| `ValueError`              | If zone indices are invalid |
| `LifxDeviceNotFoundError` | If device is not connected  |
| `LifxTimeoutError`        | If device does not respond  |
| `LifxProtocolError`       | If response is invalid      |

Example

```python
# Get colors for all zones (default)
colors = await light.get_extended_color_zones()

# Get colors for first 10 zones
colors = await light.get_extended_color_zones(0, 9)
for i, color in enumerate(colors):
    print(f"Zone {i}: {color}")
```

Source code in `src/lifx/devices/multizone.py`

````python
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
````

##### get_all_color_zones

```python
get_all_color_zones() -> list[HSBK]
```

Get colors for all zones, automatically using the best method.

This method automatically chooses between get_extended_color_zones() and get_color_zones() based on device capabilities. Always returns all zones on the device.

Always fetches from device.

| RETURNS      | DESCRIPTION                       |
| ------------ | --------------------------------- |
| `list[HSBK]` | List of HSBK colors for all zones |

| RAISES                    | DESCRIPTION                |
| ------------------------- | -------------------------- |
| `LifxDeviceNotFoundError` | If device is not connected |
| `LifxTimeoutError`        | If device does not respond |
| `LifxProtocolError`       | If response is invalid     |

Example

```python
# Get all zones (automatically uses best method)
colors = await light.get_all_color_zones()
print(f"Device has {len(colors)} zones")
```

Source code in `src/lifx/devices/multizone.py`

````python
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
````

##### set_color_zones

```python
set_color_zones(
    start: int,
    end: int,
    color: HSBK,
    duration: float = 0.0,
    apply: MultiZoneApplicationRequest = APPLY,
) -> None
```

Set color for a range of zones.

| PARAMETER  | DESCRIPTION                                                                                                                                                                                                                                  |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `start`    | Start zone index (inclusive) **TYPE:** `int`                                                                                                                                                                                                 |
| `end`      | End zone index (inclusive) **TYPE:** `int`                                                                                                                                                                                                   |
| `color`    | HSBK color to set **TYPE:** `HSBK`                                                                                                                                                                                                           |
| `duration` | Transition duration in seconds (default 0.0) **TYPE:** `float` **DEFAULT:** `0.0`                                                                                                                                                            |
| `apply`    | Application mode (default APPLY) - NO_APPLY: Don't apply immediately (use for batching) - APPLY: Apply this change and any pending changes - APPLY_ONLY: Apply only this change **TYPE:** `MultiZoneApplicationRequest` **DEFAULT:** `APPLY` |

| RAISES                    | DESCRIPTION                 |
| ------------------------- | --------------------------- |
| `ValueError`              | If zone indices are invalid |
| `LifxDeviceNotFoundError` | If device is not connected  |
| `LifxTimeoutError`        | If device does not respond  |

Example

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

Source code in `src/lifx/devices/multizone.py`

````python
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
````

##### set_extended_color_zones

```python
set_extended_color_zones(
    zone_index: int,
    colors: list[HSBK],
    duration: float = 0.0,
    apply: MultiZoneExtendedApplicationRequest = APPLY,
) -> None
```

Set colors for multiple zones efficiently (up to 82 zones per call).

This is more efficient than set_color_zones when setting different colors for many zones at once.

| PARAMETER    | DESCRIPTION                                                                                           |
| ------------ | ----------------------------------------------------------------------------------------------------- |
| `zone_index` | Starting zone index **TYPE:** `int`                                                                   |
| `colors`     | List of HSBK colors to set (max 82) **TYPE:** `list[HSBK]`                                            |
| `duration`   | Transition duration in seconds (default 0.0) **TYPE:** `float` **DEFAULT:** `0.0`                     |
| `apply`      | Application mode (default APPLY) **TYPE:** `MultiZoneExtendedApplicationRequest` **DEFAULT:** `APPLY` |

| RAISES                    | DESCRIPTION                                         |
| ------------------------- | --------------------------------------------------- |
| `ValueError`              | If colors list is too long or zone index is invalid |
| `LifxDeviceNotFoundError` | If device is not connected                          |
| `LifxTimeoutError`        | If device does not respond                          |

Example

```python
# Create a rainbow effect across zones
colors = [
    HSBK(hue=i * 36, saturation=1.0, brightness=1.0, kelvin=3500)
    for i in range(10)
]
await light.set_extended_color_zones(0, colors)
```

Source code in `src/lifx/devices/multizone.py`

````python
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
````

##### get_multizone_effect

```python
get_multizone_effect() -> MultiZoneEffect | None
```

Get current multizone effect.

Always fetches from device. Use the `multizone_effect` property to access stored value.

| RETURNS           | DESCRIPTION |
| ----------------- | ----------- |
| \`MultiZoneEffect | None\`      |

| RAISES                    | DESCRIPTION                |
| ------------------------- | -------------------------- |
| `LifxDeviceNotFoundError` | If device is not connected |
| `LifxTimeoutError`        | If device does not respond |
| `LifxProtocolError`       | If response is invalid     |

Example

```python
effect = await light.get_multizone_effect()
if effect:
    print(f"Effect: {effect.effect_type}, Speed: {effect.speed}ms")
```

Source code in `src/lifx/devices/multizone.py`

````python
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

    self._multizone_effect = result

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
````

##### set_multizone_effect

```python
set_multizone_effect(effect: MultiZoneEffect) -> None
```

Set multizone effect.

| PARAMETER | DESCRIPTION                                                |
| --------- | ---------------------------------------------------------- |
| `effect`  | MultiZone effect configuration **TYPE:** `MultiZoneEffect` |

| RAISES                    | DESCRIPTION                |
| ------------------------- | -------------------------- |
| `LifxDeviceNotFoundError` | If device is not connected |
| `LifxTimeoutError`        | If device does not respond |

Example

```python
# Apply a move effect
effect = MultiZoneEffect(
    effect_type=MultiZoneEffectType.MOVE,
    speed=5000,  # 5 seconds per cycle
    duration=0,  # Infinite
)
await light.set_multizone_effect(effect)
```

Source code in `src/lifx/devices/multizone.py`

````python
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

    # Update cached state
    result = effect if effect.effect_type != MultiZoneEffectType.OFF else None
    self._multizone_effect = result

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
````

##### stop_effect

```python
stop_effect() -> None
```

Stop any running multizone effect.

Example

```python
await light.stop_effect()
```

Source code in `src/lifx/devices/multizone.py`

````python
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
````

##### set_move_effect

```python
set_move_effect(
    speed: float = 5.0, direction: str = "forward", duration: float = 0.0
) -> None
```

Apply a moving effect that shifts colors along the strip.

| PARAMETER   | DESCRIPTION                                                                                  |
| ----------- | -------------------------------------------------------------------------------------------- |
| `speed`     | Speed in seconds per complete cycle (default 5.0) **TYPE:** `float` **DEFAULT:** `5.0`       |
| `direction` | "forward" or "backward" (default "forward") **TYPE:** `str` **DEFAULT:** `'forward'`         |
| `duration`  | Total duration in seconds (0 for infinite, default 0.0) **TYPE:** `float` **DEFAULT:** `0.0` |

| RAISES       | DESCRIPTION                                      |
| ------------ | ------------------------------------------------ |
| `ValueError` | If direction is invalid or speed is non-positive |

Example

```python
# Move forward at moderate speed
await light.set_move_effect(speed=5.0, direction="forward")

# Move backward slowly for 60 seconds
await light.set_move_effect(speed=10.0, direction="backward", duration=60.0)
```

Source code in `src/lifx/devices/multizone.py`

````python
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
````

##### apply_theme

```python
apply_theme(
    theme: Theme,
    power_on: bool = False,
    duration: float = 0,
    strategy: str | None = None,
) -> None
```

Apply a theme across zones.

Distributes theme colors evenly across the light's zones with smooth color blending between theme colors.

| PARAMETER  | DESCRIPTION                                                            |
| ---------- | ---------------------------------------------------------------------- |
| `theme`    | Theme to apply **TYPE:** `Theme`                                       |
| `power_on` | Turn on the light **TYPE:** `bool` **DEFAULT:** `False`                |
| `duration` | Transition duration in seconds **TYPE:** `float` **DEFAULT:** `0`      |
| `strategy` | Color distribution strategy (not used yet, for future) **TYPE:** \`str |

Example

```python
from lifx.theme import get_theme

theme = get_theme("evening")
await strip.apply_theme(theme, power_on=True, duration=0.5)
```

Source code in `src/lifx/devices/multizone.py`

````python
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
````

## Matrix Light

The `MatrixLight` class controls LIFX matrix devices (tiles, candle, path) with 2D zone control.

### MatrixLight

```python
MatrixLight(serial: str, ip: str, port: int = 56700)
```

Bases: `Light`

LIFX Matrix Light Device.

MatrixLight devices have 2D arrays of controllable color zones arranged in tiles. Most MatrixLight devices (LIFX Candle, LIFX Path) have a single tile. The discontinued LIFX Tile product supported up to 5 tiles in a chain (has_chain).

Zone Addressing:

- Colors are applied row-by-row starting at top-left (0,0)
- For tiles ≤64 zones: Single set64() call to frame buffer 0
- For tiles >64 zones (e.g., 16x8 = 128 zones):

1. First set64(): rect=(0,0), 64 colors, frame buffer 1
1. Second set64(): rect=(0,4), 64 colors, frame buffer 1
1. copy_frame_buffer(): Copy buffer 1 → buffer 0

Example

> > > async with await MatrixLight.from_ip("192.168.1.100") as matrix: ... # Get device chain info ... chain = await matrix.get_device_chain() ... print(f"Device has {len(chain)} tile(s)") ... ... # Set colors on first tile (8x8 = 64 zones) ... colors = [HSBK.from_rgb(255, 0, 0)] * 64 ... await matrix.set64(tile_index=0, colors=colors, width=8)

| PARAMETER | DESCRIPTION                                                       |
| --------- | ----------------------------------------------------------------- |
| `serial`  | Device serial number **TYPE:** `str`                              |
| `ip`      | Device IP address **TYPE:** `str`                                 |
| `port`    | Device port (default: 56700) **TYPE:** `int` **DEFAULT:** `56700` |

| METHOD              | DESCRIPTION                                                               |
| ------------------- | ------------------------------------------------------------------------- |
| `get_device_chain`  | Get device chain details (list of Tile objects).                          |
| `set_user_position` | Position tiles in the chain (only for devices with has_chain capability). |
| `get64`             | Get up to 64 zones of color state from a tile.                            |
| `set64`             | Set up to 64 zones of color on a tile.                                    |
| `copy_frame_buffer` | Copy frame buffer (for tiles with >64 zones).                             |
| `set_matrix_colors` | Convenience method to set all colors on a tile.                           |
| `get_tile_effect`   | Get current running tile effect.                                          |
| `set_tile_effect`   | Set tile effect with configuration.                                       |
| `apply_theme`       | Apply a theme across matrix tiles using Canvas interpolation.             |

| ATTRIBUTE      | DESCRIPTION                                         |
| -------------- | --------------------------------------------------- |
| `device_chain` | Get cached device chain. **TYPE:** \`list[TileInfo] |
| `tile_count`   | Get number of tiles in the chain. **TYPE:** \`int   |
| `tile_effect`  | Get cached tile effect. **TYPE:** \`MatrixEffect    |

Source code in `src/lifx/devices/matrix.py`

```python
def __init__(
    self,
    serial: str,
    ip: str,
    port: int = 56700,
) -> None:
    """Initialize MatrixLight device.

    Args:
        serial: Device serial number
        ip: Device IP address
        port: Device port (default: 56700)
    """
    super().__init__(serial, ip, port)
    self._device_chain: list[TileInfo] | None = None
    self._tile_effect: MatrixEffect | None = None
```

#### Attributes

##### device_chain

```python
device_chain: list[TileInfo] | None
```

Get cached device chain.

Returns None if not yet fetched. Use get_device_chain() to fetch.

##### tile_count

```python
tile_count: int | None
```

Get number of tiles in the chain.

Returns None if device chain not yet fetched.

##### tile_effect

```python
tile_effect: MatrixEffect | None
```

Get cached tile effect.

Returns None if not yet fetched. Use get_tile_effect() to fetch.

#### Functions

##### get_device_chain

```python
get_device_chain() -> list[TileInfo]
```

Get device chain details (list of Tile objects).

This method fetches the device chain information and caches it.

| RETURNS          | DESCRIPTION                                                |
| ---------------- | ---------------------------------------------------------- |
| `list[TileInfo]` | List of TileInfo objects describing each tile in the chain |

Example

> > > chain = await matrix.get_device_chain() for tile in chain: ... print(f"Tile {tile.tile_index}: {tile.width}x{tile.height}")

Source code in `src/lifx/devices/matrix.py`

```python
async def get_device_chain(self) -> list[TileInfo]:
    """Get device chain details (list of Tile objects).

    This method fetches the device chain information and caches it.

    Returns:
        List of TileInfo objects describing each tile in the chain

    Example:
        >>> chain = await matrix.get_device_chain()
        >>> for tile in chain:
        ...     print(f"Tile {tile.tile_index}: {tile.width}x{tile.height}")
    """
    _LOGGER.debug("Getting device chain for %s", self.label or self.serial)

    response: packets.Tile.StateDeviceChain = await self.connection.request(
        packets.Tile.GetDeviceChain()
    )

    # Parse tiles from response
    tiles = []
    for i, protocol_tile in enumerate(response.tile_devices):
        # Stop at first zero-width tile (indicates end of chain)
        if protocol_tile.width == 0:
            break
        tiles.append(TileInfo.from_protocol(i, protocol_tile))

    self._device_chain = tiles
    _LOGGER.debug("Device chain has %d tile(s)", len(tiles))
    return tiles
```

##### set_user_position

```python
set_user_position(tile_index: int, user_x: float, user_y: float) -> None
```

Position tiles in the chain (only for devices with has_chain capability).

| PARAMETER    | DESCRIPTION                                             |
| ------------ | ------------------------------------------------------- |
| `tile_index` | Index of the tile to position (0-based) **TYPE:** `int` |
| `user_x`     | User-defined X position **TYPE:** `float`               |
| `user_y`     | User-defined Y position **TYPE:** `float`               |

Note

Only applicable for multi-tile devices (has_chain capability). Most MatrixLight devices have a single tile and don't need positioning.

Example

> > > ###### Position second tile at coordinates (1.0, 0.0)
> > >
> > > await matrix.set_user_position(tile_index=1, user_x=1.0, user_y=0.0)

Source code in `src/lifx/devices/matrix.py`

```python
async def set_user_position(
    self, tile_index: int, user_x: float, user_y: float
) -> None:
    """Position tiles in the chain (only for devices with has_chain capability).

    Args:
        tile_index: Index of the tile to position (0-based)
        user_x: User-defined X position
        user_y: User-defined Y position

    Note:
        Only applicable for multi-tile devices (has_chain capability).
        Most MatrixLight devices have a single tile and don't need positioning.

    Example:
        >>> # Position second tile at coordinates (1.0, 0.0)
        >>> await matrix.set_user_position(tile_index=1, user_x=1.0, user_y=0.0)
    """
    _LOGGER.debug(
        "Setting tile %d position to (%f, %f) for %s",
        tile_index,
        user_x,
        user_y,
        self.label or self.serial,
    )

    await self.connection.send_packet(
        packets.Tile.SetUserPosition(
            tile_index=tile_index,
            user_x=user_x,
            user_y=user_y,
        )
    )
```

##### get64

```python
get64(
    tile_index: int, length: int, x: int, y: int, width: int, fb_index: int = 0
) -> list[HSBK]
```

Get up to 64 zones of color state from a tile.

| PARAMETER    | DESCRIPTION                                                                            |
| ------------ | -------------------------------------------------------------------------------------- |
| `tile_index` | Index of the tile (0-based) **TYPE:** `int`                                            |
| `length`     | Number of tiles to query (usually 1) **TYPE:** `int`                                   |
| `x`          | X coordinate of the rectangle (0-based) **TYPE:** `int`                                |
| `y`          | Y coordinate of the rectangle (0-based) **TYPE:** `int`                                |
| `width`      | Width of the rectangle in zones **TYPE:** `int`                                        |
| `fb_index`   | Frame buffer index (0 for display, 1 for temp buffer) **TYPE:** `int` **DEFAULT:** `0` |

| RETURNS      | DESCRIPTION                                 |
| ------------ | ------------------------------------------- |
| `list[HSBK]` | List of HSBK colors for the requested zones |

Example

> > > ###### Get colors from 8x8 tile (64 zones)
> > >
> > > colors = await matrix.get64(tile_index=0, length=1, x=0, y=0, width=8)

Source code in `src/lifx/devices/matrix.py`

```python
async def get64(
    self,
    tile_index: int,
    length: int,
    x: int,
    y: int,
    width: int,
    fb_index: int = 0,
) -> list[HSBK]:
    """Get up to 64 zones of color state from a tile.

    Args:
        tile_index: Index of the tile (0-based)
        length: Number of tiles to query (usually 1)
        x: X coordinate of the rectangle (0-based)
        y: Y coordinate of the rectangle (0-based)
        width: Width of the rectangle in zones
        fb_index: Frame buffer index (0 for display, 1 for temp buffer)

    Returns:
        List of HSBK colors for the requested zones

    Example:
        >>> # Get colors from 8x8 tile (64 zones)
        >>> colors = await matrix.get64(tile_index=0, length=1, x=0, y=0, width=8)
    """
    # Validate parameters
    if x < 0:
        raise ValueError(f"x coordinate must be non-negative, got {x}")
    if y < 0:
        raise ValueError(f"y coordinate must be non-negative, got {y}")
    if width <= 0:
        raise ValueError(f"width must be positive, got {width}")

    _LOGGER.debug(
        "Getting 64 zones from tile %d (x=%d, y=%d, width=%d, fb=%d) for %s",
        tile_index,
        x,
        y,
        width,
        fb_index,
        self.label or self.serial,
    )

    response: packets.Tile.State64 = await self.connection.request(
        packets.Tile.Get64(
            tile_index=tile_index,
            length=length,
            rect=TileBufferRect(fb_index=fb_index, x=x, y=y, width=width),
        )
    )

    # Convert protocol colors to HSBK
    colors = []
    for proto_color in response.colors:
        colors.append(
            HSBK(
                hue=proto_color.hue / 65535 * 360,
                saturation=proto_color.saturation / 65535,
                brightness=proto_color.brightness / 65535,
                kelvin=proto_color.kelvin,
            )
        )

    return colors
```

##### set64

```python
set64(
    tile_index: int,
    length: int,
    x: int,
    y: int,
    width: int,
    duration: int,
    colors: list[HSBK],
    fb_index: int = 0,
) -> None
```

Set up to 64 zones of color on a tile.

Colors are applied row-by-row starting at position (x, y). For tiles >64 zones, use multiple set64() calls with copy_frame_buffer().

| PARAMETER    | DESCRIPTION                                                                            |
| ------------ | -------------------------------------------------------------------------------------- |
| `tile_index` | Index of the tile (0-based) **TYPE:** `int`                                            |
| `length`     | Number of tiles to update (usually 1) **TYPE:** `int`                                  |
| `x`          | X coordinate of the rectangle (0-based) **TYPE:** `int`                                |
| `y`          | Y coordinate of the rectangle (0-based) **TYPE:** `int`                                |
| `width`      | Width of the rectangle in zones **TYPE:** `int`                                        |
| `duration`   | Transition duration in milliseconds **TYPE:** `int`                                    |
| `colors`     | List of HSBK colors (up to 64) **TYPE:** `list[HSBK]`                                  |
| `fb_index`   | Frame buffer index (0 for display, 1 for temp buffer) **TYPE:** `int` **DEFAULT:** `0` |

Example

> > > ###### Set 8x8 tile to red
> > >
> > > colors = [HSBK.from_rgb(255, 0, 0)] * 64 await matrix.set64( ... tile_index=0, length=1, x=0, y=0, width=8, duration=0, colors=colors ... )

Source code in `src/lifx/devices/matrix.py`

```python
async def set64(
    self,
    tile_index: int,
    length: int,
    x: int,
    y: int,
    width: int,
    duration: int,
    colors: list[HSBK],
    fb_index: int = 0,
) -> None:
    """Set up to 64 zones of color on a tile.

    Colors are applied row-by-row starting at position (x, y).
    For tiles >64 zones, use multiple set64() calls with copy_frame_buffer().

    Args:
        tile_index: Index of the tile (0-based)
        length: Number of tiles to update (usually 1)
        x: X coordinate of the rectangle (0-based)
        y: Y coordinate of the rectangle (0-based)
        width: Width of the rectangle in zones
        duration: Transition duration in milliseconds
        colors: List of HSBK colors (up to 64)
        fb_index: Frame buffer index (0 for display, 1 for temp buffer)

    Example:
        >>> # Set 8x8 tile to red
        >>> colors = [HSBK.from_rgb(255, 0, 0)] * 64
        >>> await matrix.set64(
        ...     tile_index=0, length=1, x=0, y=0, width=8, duration=0, colors=colors
        ... )
    """
    # Validate parameters
    if x < 0:
        raise ValueError(f"x coordinate must be non-negative, got {x}")
    if y < 0:
        raise ValueError(f"y coordinate must be non-negative, got {y}")
    if width <= 0:
        raise ValueError(f"width must be positive, got {width}")

    _LOGGER.debug(
        "Setting 64 zones on tile %d (x=%d, y=%d, width=%d, fb=%d, "
        "duration=%d) for %s",
        tile_index,
        x,
        y,
        width,
        fb_index,
        duration,
        self.label or self.serial,
    )

    # Convert HSBK colors to protocol format
    proto_colors = []
    for color in colors:
        proto_colors.append(
            LightHsbk(
                hue=int(color.hue / 360 * 65535),
                saturation=int(color.saturation * 65535),
                brightness=int(color.brightness * 65535),
                kelvin=color.kelvin,
            )
        )

    # Pad to 64 colors if needed
    while len(proto_colors) < 64:
        proto_colors.append(LightHsbk(0, 0, 0, 3500))

    await self.connection.send_packet(
        packets.Tile.Set64(
            tile_index=tile_index,
            length=length,
            rect=TileBufferRect(fb_index=fb_index, x=x, y=y, width=width),
            duration=duration,
            colors=proto_colors,
        )
    )
```

##### copy_frame_buffer

```python
copy_frame_buffer(
    tile_index: int, source_fb: int = 1, target_fb: int = 0
) -> None
```

Copy frame buffer (for tiles with >64 zones).

This is used for tiles with more than 64 zones. After setting colors in the temporary buffer (fb=1), copy to the display buffer (fb=0).

| PARAMETER    | DESCRIPTION                                                            |
| ------------ | ---------------------------------------------------------------------- |
| `tile_index` | Index of the tile (0-based) **TYPE:** `int`                            |
| `source_fb`  | Source frame buffer index (usually 1) **TYPE:** `int` **DEFAULT:** `1` |
| `target_fb`  | Target frame buffer index (usually 0) **TYPE:** `int` **DEFAULT:** `0` |

Example

> > > ###### For 16x8 tile (128 zones):
> > >
> > > ###### 1. Set first 64 zones to buffer 1
> > >
> > > await matrix.set64( ... tile_index=0, ... length=1, ... x=0, ... y=0, ... width=16, ... duration=0, ... colors=colors[:64], ... fb_index=1, ... )
> > >
> > > ###### 2. Set second 64 zones to buffer 1
> > >
> > > await matrix.set64( ... tile_index=0, ... length=1, ... x=0, ... y=4, ... width=16, ... duration=0, ... colors=colors[64:], ... fb_index=1, ... )
> > >
> > > ###### 3. Copy buffer 1 to buffer 0 (display)
> > >
> > > await matrix.copy_frame_buffer(tile_index=0, source_fb=1, target_fb=0)

Source code in `src/lifx/devices/matrix.py`

```python
async def copy_frame_buffer(
    self, tile_index: int, source_fb: int = 1, target_fb: int = 0
) -> None:
    """Copy frame buffer (for tiles with >64 zones).

    This is used for tiles with more than 64 zones. After setting colors
    in the temporary buffer (fb=1), copy to the display buffer (fb=0).

    Args:
        tile_index: Index of the tile (0-based)
        source_fb: Source frame buffer index (usually 1)
        target_fb: Target frame buffer index (usually 0)

    Example:
        >>> # For 16x8 tile (128 zones):
        >>> # 1. Set first 64 zones to buffer 1
        >>> await matrix.set64(
        ...     tile_index=0,
        ...     length=1,
        ...     x=0,
        ...     y=0,
        ...     width=16,
        ...     duration=0,
        ...     colors=colors[:64],
        ...     fb_index=1,
        ... )
        >>> # 2. Set second 64 zones to buffer 1
        >>> await matrix.set64(
        ...     tile_index=0,
        ...     length=1,
        ...     x=0,
        ...     y=4,
        ...     width=16,
        ...     duration=0,
        ...     colors=colors[64:],
        ...     fb_index=1,
        ... )
        >>> # 3. Copy buffer 1 to buffer 0 (display)
        >>> await matrix.copy_frame_buffer(tile_index=0, source_fb=1, target_fb=0)
    """
    _LOGGER.debug(
        "Copying frame buffer %d -> %d for tile %d on %s",
        source_fb,
        target_fb,
        tile_index,
        self.label or self.serial,
    )

    # Get tile dimensions for the copy operation
    if self._device_chain is None:
        await self.get_device_chain()

    if self._device_chain is None or tile_index >= len(self._device_chain):
        raise ValueError(f"Invalid tile_index {tile_index}")

    tile = self._device_chain[tile_index]

    await self.connection.send_packet(
        packets.Tile.CopyFrameBuffer(
            tile_index=tile_index,
            length=1,
            src_fb_index=source_fb,
            dst_fb_index=target_fb,
            src_x=0,
            src_y=0,
            dst_x=0,
            dst_y=0,
            width=tile.width,
            height=tile.height,
            duration=0,
        )
    )
```

##### set_matrix_colors

```python
set_matrix_colors(
    tile_index: int, colors: list[HSBK], duration: int = 0
) -> None
```

Convenience method to set all colors on a tile.

If all colors are the same, uses SetColor() packet which sets all zones across all tiles. Otherwise, automatically handles tiles with >64 zones using frame buffer strategy.

| PARAMETER    | DESCRIPTION                                                                     |
| ------------ | ------------------------------------------------------------------------------- |
| `tile_index` | Index of the tile (0-based) **TYPE:** `int`                                     |
| `colors`     | List of HSBK colors (length must match tile total_zones) **TYPE:** `list[HSBK]` |
| `duration`   | Transition duration in milliseconds **TYPE:** `int` **DEFAULT:** `0`            |

Example

> > > ###### Set entire tile to solid red (uses SetColor packet)
> > >
> > > colors = [HSBK.from_rgb(255, 0, 0)] * 64 await matrix.set_matrix_colors(tile_index=0, colors=colors)
> > >
> > > ###### Set 8x8 tile to gradient (uses set64 with zones)
> > >
> > > colors = [HSBK(i * 360 / 64, 1.0, 1.0, 3500) for i in range(64)] await matrix.set_matrix_colors(tile_index=0, colors=colors)

Source code in `src/lifx/devices/matrix.py`

```python
async def set_matrix_colors(
    self, tile_index: int, colors: list[HSBK], duration: int = 0
) -> None:
    """Convenience method to set all colors on a tile.

    If all colors are the same, uses SetColor() packet which sets all zones
    across all tiles. Otherwise, automatically handles tiles with >64 zones
    using frame buffer strategy.

    Args:
        tile_index: Index of the tile (0-based)
        colors: List of HSBK colors (length must match tile total_zones)
        duration: Transition duration in milliseconds

    Example:
        >>> # Set entire tile to solid red (uses SetColor packet)
        >>> colors = [HSBK.from_rgb(255, 0, 0)] * 64
        >>> await matrix.set_matrix_colors(tile_index=0, colors=colors)

        >>> # Set 8x8 tile to gradient (uses set64 with zones)
        >>> colors = [HSBK(i * 360 / 64, 1.0, 1.0, 3500) for i in range(64)]
        >>> await matrix.set_matrix_colors(tile_index=0, colors=colors)
    """
    # Get device chain to determine tile dimensions
    if self._device_chain is None:
        await self.get_device_chain()

    if not self._device_chain or tile_index >= len(self._device_chain):
        raise ValueError(f"Invalid tile_index: {tile_index}")

    tile = self._device_chain[tile_index]

    if len(colors) != tile.total_zones:
        raise ValueError(
            f"Color count mismatch: expected {tile.total_zones}, got {len(colors)}"
        )

    # Check if all colors are the same
    first_color = colors[0]
    all_same = all(
        c.hue == first_color.hue
        and c.saturation == first_color.saturation
        and c.brightness == first_color.brightness
        and c.kelvin == first_color.kelvin
        for c in colors
    )

    if all_same:
        # All zones same color - use SetColor packet (much faster!)
        _LOGGER.debug(
            "All zones same color, using SetColor packet for tile %d",
            tile_index,
        )
        await self.set_color(first_color, duration=duration / 1000.0)
        return

    if tile.requires_frame_buffer:
        # Tile has >64 zones, use frame buffer strategy
        _LOGGER.debug(
            "Using frame buffer strategy for tile %d (%dx%d = %d zones)",
            tile_index,
            tile.width,
            tile.height,
            tile.total_zones,
        )

        # Calculate rows per batch (64 zones / width)
        rows_per_batch = 64 // tile.width
        total_batches = (tile.height + rows_per_batch - 1) // rows_per_batch

        for batch in range(total_batches):
            start_row = batch * rows_per_batch
            end_row = min(start_row + rows_per_batch, tile.height)

            # Extract colors for this batch
            start_idx = start_row * tile.width
            end_idx = end_row * tile.width
            batch_colors = colors[start_idx:end_idx]

            # Set colors to frame buffer 1
            await self.set64(
                tile_index=tile_index,
                length=1,
                x=0,
                y=start_row,
                width=tile.width,
                duration=duration if batch == total_batches - 1 else 0,
                colors=batch_colors,
                fb_index=1,
            )

        # Copy frame buffer 1 to 0 (display)
        await self.copy_frame_buffer(
            tile_index=tile_index, source_fb=1, target_fb=0
        )
    else:
        # Tile has ≤64 zones, single set64() call
        await self.set64(
            tile_index=tile_index,
            length=1,
            x=0,
            y=0,
            width=tile.width,
            duration=duration,
            colors=colors,
        )
```

##### get_tile_effect

```python
get_tile_effect() -> MatrixEffect
```

Get current running tile effect.

| RETURNS        | DESCRIPTION                                      |
| -------------- | ------------------------------------------------ |
| `MatrixEffect` | MatrixEffect describing the current effect state |

Example

> > > effect = await matrix.get_tile_effect() print(f"Effect type: {effect.effect_type}")

Source code in `src/lifx/devices/matrix.py`

```python
async def get_tile_effect(self) -> MatrixEffect:
    """Get current running tile effect.

    Returns:
        MatrixEffect describing the current effect state

    Example:
        >>> effect = await matrix.get_tile_effect()
        >>> print(f"Effect type: {effect.effect_type}")
    """
    _LOGGER.debug("Getting tile effect for %s", self.label or self.serial)

    response: packets.Tile.StateEffect = await self.connection.request(
        packets.Tile.GetEffect()
    )

    # Convert protocol effect to MatrixEffect
    palette = []
    for proto_color in response.settings.palette[: response.settings.palette_count]:
        palette.append(
            HSBK(
                hue=proto_color.hue / 65535 * 360,
                saturation=proto_color.saturation / 65535,
                brightness=proto_color.brightness / 65535,
                kelvin=proto_color.kelvin,
            )
        )

    effect = MatrixEffect(
        effect_type=response.settings.effect_type,
        speed=response.settings.speed,
        duration=response.settings.duration,
        palette=palette if palette else None,
        sky_type=response.settings.parameter.sky_type,
        cloud_saturation_min=response.settings.parameter.cloud_saturation_min,
        cloud_saturation_max=response.settings.parameter.cloud_saturation_max,
    )

    self._tile_effect = effect
    return effect
```

##### set_tile_effect

```python
set_tile_effect(
    effect_type: TileEffectType,
    speed: int = 3000,
    duration: int = 0,
    palette: list[HSBK] | None = None,
    sky_type: TileEffectSkyType = SUNRISE,
    cloud_saturation_min: int = 0,
    cloud_saturation_max: int = 0,
) -> None
```

Set tile effect with configuration.

| PARAMETER              | DESCRIPTION                                                                                    |
| ---------------------- | ---------------------------------------------------------------------------------------------- |
| `effect_type`          | Type of effect (OFF, MORPH, FLAME, SKY) **TYPE:** `TileEffectType`                             |
| `speed`                | Effect speed in milliseconds (default: 3000) **TYPE:** `int` **DEFAULT:** `3000`               |
| `duration`             | Total effect duration in nanoseconds (0 for infinite) **TYPE:** `int` **DEFAULT:** `0`         |
| `palette`              | Color palette for the effect (max 16 colors) **TYPE:** \`list[HSBK]                            |
| `sky_type`             | Sky effect type (SUNRISE, SUNSET, CLOUDS) **TYPE:** `TileEffectSkyType` **DEFAULT:** `SUNRISE` |
| `cloud_saturation_min` | Minimum cloud saturation (0-255, for CLOUDS) **TYPE:** `int` **DEFAULT:** `0`                  |
| `cloud_saturation_max` | Maximum cloud saturation (0-255, for CLOUDS) **TYPE:** `int` **DEFAULT:** `0`                  |

Example

> > > ###### Set MORPH effect with rainbow palette
> > >
> > > rainbow = [ ... HSBK(0, 1.0, 1.0, 3500), # Red ... HSBK(60, 1.0, 1.0, 3500), # Yellow ... HSBK(120, 1.0, 1.0, 3500), # Green ... HSBK(240, 1.0, 1.0, 3500), # Blue ... ] await matrix.set_tile_effect( ... effect_type=TileEffectType.MORPH, ... speed=5000, ... palette=rainbow, ... )

Source code in `src/lifx/devices/matrix.py`

```python
async def set_tile_effect(
    self,
    effect_type: TileEffectType,
    speed: int = 3000,
    duration: int = 0,
    palette: list[HSBK] | None = None,
    sky_type: TileEffectSkyType = TileEffectSkyType.SUNRISE,
    cloud_saturation_min: int = 0,
    cloud_saturation_max: int = 0,
) -> None:
    """Set tile effect with configuration.

    Args:
        effect_type: Type of effect (OFF, MORPH, FLAME, SKY)
        speed: Effect speed in milliseconds (default: 3000)
        duration: Total effect duration in nanoseconds (0 for infinite)
        palette: Color palette for the effect (max 16 colors)
        sky_type: Sky effect type (SUNRISE, SUNSET, CLOUDS)
        cloud_saturation_min: Minimum cloud saturation (0-255, for CLOUDS)
        cloud_saturation_max: Maximum cloud saturation (0-255, for CLOUDS)

    Example:
        >>> # Set MORPH effect with rainbow palette
        >>> rainbow = [
        ...     HSBK(0, 1.0, 1.0, 3500),  # Red
        ...     HSBK(60, 1.0, 1.0, 3500),  # Yellow
        ...     HSBK(120, 1.0, 1.0, 3500),  # Green
        ...     HSBK(240, 1.0, 1.0, 3500),  # Blue
        ... ]
        >>> await matrix.set_tile_effect(
        ...     effect_type=TileEffectType.MORPH,
        ...     speed=5000,
        ...     palette=rainbow,
        ... )
    """
    _LOGGER.debug(
        "Setting tile effect %s (speed=%d) for %s",
        effect_type,
        speed,
        self.label or self.serial,
    )

    # Create and validate MatrixEffect
    effect = MatrixEffect(
        effect_type=effect_type,
        speed=speed,
        duration=duration,
        palette=palette,
        sky_type=sky_type,
        cloud_saturation_min=cloud_saturation_min,
        cloud_saturation_max=cloud_saturation_max,
    )

    # Convert to protocol format
    # Note: palette is guaranteed to be non-None by MatrixEffect.__post_init__
    palette = effect.palette if effect.palette is not None else []
    proto_palette = []
    for color in palette:
        proto_palette.append(
            LightHsbk(
                hue=int(color.hue / 360 * 65535),
                saturation=int(color.saturation * 65535),
                brightness=int(color.brightness * 65535),
                kelvin=color.kelvin,
            )
        )

    # Pad palette to 16 colors
    while len(proto_palette) < 16:
        proto_palette.append(LightHsbk(0, 0, 0, 3500))

    settings = TileEffectSettings(
        instanceid=0,
        effect_type=effect.effect_type,
        speed=effect.speed,
        duration=effect.duration,
        parameter=TileEffectParameter(
            sky_type=effect.sky_type,
            cloud_saturation_min=effect.cloud_saturation_min,
            cloud_saturation_max=effect.cloud_saturation_max,
        ),
        palette_count=len(palette),
        palette=proto_palette,
    )

    await self.connection.send_packet(packets.Tile.SetEffect(settings=settings))
    self._tile_effect = effect
```

##### apply_theme

```python
apply_theme(
    theme: Theme, power_on: bool = False, duration: float = 0.0
) -> None
```

Apply a theme across matrix tiles using Canvas interpolation.

Distributes theme colors across the tile matrix with smooth color blending using the Canvas API for visually pleasing transitions.

| PARAMETER  | DESCRIPTION                                                         |
| ---------- | ------------------------------------------------------------------- |
| `theme`    | Theme to apply **TYPE:** `Theme`                                    |
| `power_on` | Turn on the light **TYPE:** `bool` **DEFAULT:** `False`             |
| `duration` | Transition duration in seconds **TYPE:** `float` **DEFAULT:** `0.0` |

Example

```python
from lifx.theme import get_theme

theme = get_theme("evening")
await matrix.apply_theme(theme, power_on=True, duration=0.5)
```

Source code in `src/lifx/devices/matrix.py`

````python
async def apply_theme(
    self,
    theme: "Theme",
    power_on: bool = False,
    duration: float = 0.0,
) -> None:
    """Apply a theme across matrix tiles using Canvas interpolation.

    Distributes theme colors across the tile matrix with smooth color blending
    using the Canvas API for visually pleasing transitions.

    Args:
        theme: Theme to apply
        power_on: Turn on the light
        duration: Transition duration in seconds

    Example:
        ```python
        from lifx.theme import get_theme

        theme = get_theme("evening")
        await matrix.apply_theme(theme, power_on=True, duration=0.5)
        ```
    """
    from lifx.theme.canvas import Canvas

    # Get device chain
    tiles = await self.get_device_chain()

    if not tiles:
        return

    # Create canvas and populate with theme colors
    canvas = Canvas()
    for tile in tiles:
        canvas.add_points_for_tile(None, theme)
    canvas.shuffle_points()
    canvas.blur_by_distance()

    # Check if light is on
    is_on = await self.get_power()

    # Apply colors to each tile
    for tile in tiles:
        # Extract tile colors from canvas as 1D list
        colors = canvas.points_for_tile(None, width=tile.width, height=tile.height)

        # Apply with appropriate timing
        if power_on and not is_on:
            await self.set_matrix_colors(tile.tile_index, colors, duration=0)
        else:
            await self.set_matrix_colors(
                tile.tile_index, colors, duration=int(duration * 1000)
            )

    # Turn on light if requested and currently off
    if power_on and not is_on:
        await self.set_power(True, duration=duration)
````

## Device Properties

### MAC Address

The `mac_address` property provides the device's MAC address, calculated from the serial number and host firmware version. The calculation is performed automatically when the device is used as a context manager or when `get_host_firmware()` is called.

**Calculation Logic** (based on host firmware major version):

- **Version 2 or 4**: MAC address matches the serial number
- **Version 3**: MAC address is the serial number with the least significant byte incremented by 1 (with wraparound from 0xFF to 0x00)
- **Unknown versions**: Defaults to the serial number

The MAC address is returned in colon-separated lowercase hexadecimal format (e.g., `d0:73:d5:01:02:03`) to visually distinguish it from the serial number format.

```python
from lifx import Device

async def main():
    async with await Device.from_ip("192.168.1.100") as device:
        # MAC address is automatically calculated during setup
        if device.mac_address:
            print(f"Serial: {device.serial}")
            print(f"MAC:    {device.mac_address}")

        # Returns None before host_firmware is fetched
        assert device.mac_address is not None
```

## Examples

### Basic Light Control

```python
from lifx import Light, Colors


async def main():
    async with await Light.from_ip("192.168.1.100") as light:
        # Turn on and set color
        await light.set_power(True)
        await light.set_color(Colors.BLUE, duration=1.0)

        # Get device info
        label = await light.get_label()
        print(f"Controlling: {label}")
```

### Light Effects

```python
from lifx import Light, Colors


async def main():
    async with await Light.from_ip("192.168.1.100") as light:
        # Pulse effect
        await light.pulse(Colors.RED, period=1.0, cycles=5)

        # Breathe effect
        await light.breathe(Colors.BLUE, period=2.0, cycles=3)
```

### HEV Light Control (Anti-Bacterial Cleaning)

```python
from lifx import HevLight


async def main():
    async with await HevLight.from_ip("192.168.1.100") as light:
        # Start a 2-hour cleaning cycle
        await light.set_hev_cycle(enable=True, duration_seconds=7200)

        # Check cycle status
        state = await light.get_hev_cycle()
        if state.is_running:
            print(f"Cleaning: {state.remaining_s}s remaining")

        # Configure default settings
        await light.set_hev_config(indication=True, duration_seconds=7200)
```

### Infrared Light Control (Night Vision)

```python
from lifx import InfraredLight


async def main():
    async with await InfraredLight.from_ip("192.168.1.100") as light:
        # Set infrared brightness to 50%
        await light.set_infrared(0.5)

        # Get current infrared brightness
        brightness = await light.get_infrared()
        print(f"IR brightness: {brightness * 100}%")
```

### MultiZone Control

```python
from lifx import find_lights, Colors


async def main():
    async with find_lights() as lights:
        for light in lights:
            # Get all zones - automatically uses best method
            colors = await light.get_all_color_zones()
            print(f"Device has {len(colors)} zones")
```

### Tile Control

```python
from lifx import find_lights, HSBK


async def main():
    async with find_lights() as lights:
        for light in lights:
            if light.has_matrix:
                # Set a gradient across the tile
                colors = [
                    HSBK(hue=h, saturation=1.0, brightness=0.5, kelvin=3500)
                    for h in range(0, 360, 10)
                ]
                await light.set_tile_colors(colors)
```
