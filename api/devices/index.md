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
    timeout: float = 1.0,
    max_retries: int = 3,
)
```

Base class for LIFX devices.

This class provides common functionality for all LIFX devices:

- Connection management
- Basic device queries (label, power, version, info)
- State storage with timestamps (no automatic expiration)

All properties return a tuple of (value, timestamp) or None if never fetched. Callers can use the timestamp to determine if data needs refreshing.

Example

```python
device = Device(serial="d073d5123456", ip="192.168.1.100")

async with device:
    # Get device label
    label = await device.get_label()
    print(f"Device: {label}")

    # Check label and its age
    if device.label is not None:
        label_value, updated_at = device.label
        age = time.time() - updated_at
        print(f"Label '{label_value}' is {age:.1f}s old")

    # Turn on device and auto-refresh power state
    await device.set_power(True, refresh=True)

    # Get power state with timestamp
    power_result = device.power
    if power_result:
        is_on, timestamp = power_result
        print(f"Power: {'ON' if is_on else 'OFF'}")
```

| PARAMETER     | DESCRIPTION                                                                            |
| ------------- | -------------------------------------------------------------------------------------- |
| `serial`      | Device serial number as 12-digit hex string (e.g., "d073d5123456") **TYPE:** `str`     |
| `ip`          | Device IP address **TYPE:** `str`                                                      |
| `port`        | Device UDP port **TYPE:** `int` **DEFAULT:** `LIFX_UDP_PORT`                           |
| `timeout`     | Overall timeout for network requests in seconds **TYPE:** `float` **DEFAULT:** `1.0`   |
| `max_retries` | Maximum number of retry attempts for network requests **TYPE:** `int` **DEFAULT:** `3` |

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

| ATTRIBUTE       | DESCRIPTION                                                                                  |
| --------------- | -------------------------------------------------------------------------------------------- |
| `capabilities`  | Get device product capabilities. **TYPE:** \`ProductInfo                                     |
| `label`         | Get stored label with timestamp if available. **TYPE:** \`tuple[str, float]                  |
| `power`         | Get stored power state with timestamp if available. **TYPE:** \`tuple[bool, float]           |
| `version`       | Get stored version with timestamp if available. **TYPE:** \`tuple[DeviceVersion, float]      |
| `host_firmware` | Get stored host firmware with timestamp if available. **TYPE:** \`tuple[FirmwareInfo, float] |
| `wifi_firmware` | Get stored wifi firmware with timestamp if available. **TYPE:** \`tuple[FirmwareInfo, float] |
| `location`      | Get stored location name with timestamp if available. **TYPE:** \`tuple[str, float]          |
| `group`         | Get stored group name with timestamp if available. **TYPE:** \`tuple[str, float]             |
| `model`         | Get LIFX friendly model name if available. **TYPE:** \`str                                   |

Source code in `src/lifx/devices/base.py`

```python
def __init__(
    self,
    serial: str,
    ip: str,
    port: int = LIFX_UDP_PORT,
    timeout: float = 1.0,
    max_retries: int = 3,
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

    # State storage: Each value stored as (value, timestamp) tuple
    # Values never expire automatically - caller decides when to refresh
    self._label: tuple[str, float] | None = None
    self._power: tuple[bool, float] | None = None
    self._version: tuple[DeviceVersion, float] | None = None
    self._host_firmware: tuple[FirmwareInfo, float] | None = None
    self._wifi_firmware: tuple[FirmwareInfo, float] | None = None
    self._location: tuple[LocationInfo, float] | None = None
    self._group: tuple[GroupInfo, float] | None = None

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
label: tuple[str, float] | None
```

Get stored label with timestamp if available.

Use get_label() to fetch from device.

| RETURNS             | DESCRIPTION |
| ------------------- | ----------- |
| \`tuple[str, float] | None\`      |

##### power

```python
power: tuple[bool, float] | None
```

Get stored power state with timestamp if available.

Use get_power() to fetch from device.

| RETURNS              | DESCRIPTION |
| -------------------- | ----------- |
| \`tuple[bool, float] | None\`      |

##### version

```python
version: tuple[DeviceVersion, float] | None
```

Get stored version with timestamp if available.

Use get_version() to fetch from device.

| RETURNS                       | DESCRIPTION |
| ----------------------------- | ----------- |
| \`tuple[DeviceVersion, float] | None\`      |

##### host_firmware

```python
host_firmware: tuple[FirmwareInfo, float] | None
```

Get stored host firmware with timestamp if available.

Use get_host_firmware() to fetch from device.

| RETURNS                      | DESCRIPTION |
| ---------------------------- | ----------- |
| \`tuple[FirmwareInfo, float] | None\`      |

##### wifi_firmware

```python
wifi_firmware: tuple[FirmwareInfo, float] | None
```

Get stored wifi firmware with timestamp if available.

Use get_wifi_firmware() to fetch from device.

| RETURNS                      | DESCRIPTION |
| ---------------------------- | ----------- |
| \`tuple[FirmwareInfo, float] | None\`      |

##### location

```python
location: tuple[str, float] | None
```

Get stored location name with timestamp if available.

Use get_location() to fetch from device.

| RETURNS             | DESCRIPTION |
| ------------------- | ----------- |
| \`tuple[str, float] | None\`      |

##### group

```python
group: tuple[str, float] | None
```

Get stored group name with timestamp if available.

Use get_group() to fetch from device.

| RETURNS             | DESCRIPTION |
| ------------------- | ----------- |
| \`tuple[str, float] | None\`      |

##### model

```python
model: str | None
```

Get LIFX friendly model name if available.

| RETURNS | DESCRIPTION |
| ------- | ----------- |
| \`str   | None\`      |

#### Functions

##### from_ip

```python
from_ip(
    ip: str,
    port: int = LIFX_UDP_PORT,
    serial: str | None = None,
    timeout: float = 1.0,
) -> Self
```

Create and return an instance for the given IP address.

This is a convenience class method for connecting to a known device by IP address. The returned instance can be used as a context manager.

| PARAMETER | DESCRIPTION                                                                      |
| --------- | -------------------------------------------------------------------------------- |
| `ip`      | IP address of the device **TYPE:** `str`                                         |
| `port`    | Port number (default LIFX_UDP_PORT) **TYPE:** `int` **DEFAULT:** `LIFX_UDP_PORT` |
| `serial`  | Serial number as 12-digit hex string **TYPE:** \`str                             |
| `timeout` | Request timeout for this device instance **TYPE:** `float` **DEFAULT:** `1.0`    |

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
    timeout: float = 1.0,
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
        response = await temp_conn.request(packets.Device.GetService(), timeout=2.0)
        if response and isinstance(response, packets.Device.StateService):
            if temp_conn.serial and temp_conn.serial != "000000000000":
                return cls(
                    serial=temp_conn.serial, ip=ip, port=port, timeout=timeout
                )
    else:
        return cls(serial=serial, ip=ip, port=port, timeout=timeout)

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

# Or use stored value
if device.label:
    label, timestamp = device.label
    print(f"Stored label: {label}")
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

        # Or use stored value
        if device.label:
            label, timestamp = device.label
            print(f"Stored label: {label}")
        ```
    """
    # Request automatically unpacks and decodes label
    state = await self.connection.request(packets.Device.GetLabel())

    # Store label with timestamp
    self._label = (state.label, time.time())
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

    # Update state with timestamp
    self._label = (label, time.time())
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
get_power() -> bool
```

Get device power state.

Always fetches from device. Use the `power` property to access stored value.

| RETURNS | DESCRIPTION                                   |
| ------- | --------------------------------------------- |
| `bool`  | True if device is powered on, False otherwise |

| RAISES                    | DESCRIPTION                |
| ------------------------- | -------------------------- |
| `LifxDeviceNotFoundError` | If device is not connected |
| `LifxTimeoutError`        | If device does not respond |
| `LifxProtocolError`       | If response is invalid     |

Example

```python
is_on = await device.get_power()
print(f"Power: {'ON' if is_on else 'OFF'}")
```

Source code in `src/lifx/devices/base.py`

````python
async def get_power(self) -> bool:
    """Get device power state.

    Always fetches from device. Use the `power` property to access stored value.

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
    # Request automatically unpacks response
    state = await self.connection.request(packets.Device.GetPower())

    # Power level is uint16 (0 or 65535)
    is_on = state.level > 0

    self._power = (is_on, time.time())
    _LOGGER.debug(
        {
            "class": "Device",
            "method": "get_power",
            "action": "query",
            "reply": {"level": state.level},
        }
    )
    return is_on
````

##### set_power

```python
set_power(on: bool) -> None
```

Set device power state.

| PARAMETER | DESCRIPTION                                         |
| --------- | --------------------------------------------------- |
| `on`      | True to turn on, False to turn off **TYPE:** `bool` |

| RAISES                    | DESCRIPTION                |
| ------------------------- | -------------------------- |
| `LifxDeviceNotFoundError` | If device is not connected |
| `LifxTimeoutError`        | If device does not respond |

Example

```python
# Turn on device
await device.set_power(True)
```

Source code in `src/lifx/devices/base.py`

````python
async def set_power(self, on: bool) -> None:
    """Set device power state.

    Args:
        on: True to turn on, False to turn off

    Raises:
        LifxDeviceNotFoundError: If device is not connected
        LifxTimeoutError: If device does not respond

    Example:
        ```python
        # Turn on device
        await device.set_power(True)
        ```
    """
    # Power level: 0 for off, 65535 for on
    level = 65535 if on else 0

    # Request automatically handles acknowledgement
    await self.connection.request(
        packets.Device.SetPower(level=level),
    )

    # Update state with timestamp
    self._power = (on, time.time())
    _LOGGER.debug(
        {
            "class": "Device",
            "method": "set_power",
            "action": "change",
            "values": {"level": level},
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

    self._version = (version, time.time())

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

    self._host_firmware = (firmware, time.time())

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

    self._wifi_firmware = (firmware, time.time())

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

    self._location = (location, time.time())

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
set_location(label: str, *, discover_timeout: float = 3.0) -> None
```

Set device location information.

Automatically discovers devices on the network to check if any device already has the target location label. If found, reuses that existing UUID to ensure devices with the same label share the same location UUID. If not found, generates a new UUID for this label.

| PARAMETER          | DESCRIPTION                                                                                |
| ------------------ | ------------------------------------------------------------------------------------------ |
| `label`            | Location label (max 32 characters) **TYPE:** `str`                                         |
| `discover_timeout` | Timeout for device discovery in seconds (default 3.0) **TYPE:** `float` **DEFAULT:** `3.0` |

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

    # Update state with timestamp
    location_info = LocationInfo(
        location=location_uuid_to_use, label=label, updated_at=updated_at
    )
    self._location = (location_info, time.time())
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

    self._group = (group, time.time())

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
set_group(label: str, *, discover_timeout: float = 3.0) -> None
```

Set device group information.

Automatically discovers devices on the network to check if any device already has the target group label. If found, reuses that existing UUID to ensure devices with the same label share the same group UUID. If not found, generates a new UUID for this label.

| PARAMETER          | DESCRIPTION                                                                                |
| ------------------ | ------------------------------------------------------------------------------------------ |
| `label`            | Group label (max 32 characters) **TYPE:** `str`                                            |
| `discover_timeout` | Timeout for device discovery in seconds (default 3.0) **TYPE:** `float` **DEFAULT:** `3.0` |

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

    # Update state with timestamp
    group_info = GroupInfo(
        group=group_uuid_to_use, label=label, updated_at=updated_at
    )
    self._group = (group_info, time.time())
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

| ATTRIBUTE    | DESCRIPTION                                                                        |
| ------------ | ---------------------------------------------------------------------------------- |
| `color`      | Get stored light color with timestamp if available. **TYPE:** \`tuple[HSBK, float] |
| `min_kelvin` | Get the minimum supported kelvin value if available. **TYPE:** \`int               |
| `max_kelvin` | Get the maximum supported kelvin value if available. **TYPE:** \`int               |

Source code in `src/lifx/devices/light.py`

```python
def __init__(self, *args, **kwargs) -> None:
    """Initialize Light with additional state attributes."""
    super().__init__(*args, **kwargs)
    # Light-specific state storage
    self._color: tuple[HSBK, float] | None = None
```

#### Attributes

##### color

```python
color: tuple[HSBK, float] | None
```

Get stored light color with timestamp if available.

| RETURNS              | DESCRIPTION |
| -------------------- | ----------- |
| \`tuple[HSBK, float] | None\`      |
| \`tuple[HSBK, float] | None\`      |

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
get_color() -> tuple[HSBK, bool, str]
```

Get current light color, power, and label.

Always fetches from device. Use the `color` property to access stored value.

Returns a tuple containing:

- color: HSBK color
- power: Power state (True=on, False=off)
- label: Device label/name

| RETURNS                  | DESCRIPTION                    |
| ------------------------ | ------------------------------ |
| `tuple[HSBK, bool, str]` | Tuple of (color, power, label) |

| RAISES                    | DESCRIPTION                |
| ------------------------- | -------------------------- |
| `LifxDeviceNotFoundError` | If device is not connected |
| `LifxTimeoutError`        | If device does not respond |
| `LifxProtocolError`       | If response is invalid     |

Example

```python
color, power, label = await light.get_color()
print(f"{label}: Hue: {color.hue}°, Power: {power}")
```

Source code in `src/lifx/devices/light.py`

````python
async def get_color(self) -> tuple[HSBK, bool, str]:
    """Get current light color, power, and label.

    Always fetches from device. Use the `color` property to access stored value.

    Returns a tuple containing:
    - color: HSBK color
    - power: Power state (True=on, False=off)
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
        print(f"{label}: Hue: {color.hue}°, Power: {power}")
        ```
    """
    # Request automatically unpacks response and decodes labels
    state = await self.connection.request(packets.Light.GetColor())

    # Convert from protocol HSBK to user-friendly HSBK
    color = HSBK.from_protocol(state.color)
    power = state.power > 0
    label = state.label

    # Store color and other fields from StateColor response with timestamps
    import time

    timestamp = time.time()
    self._color = (color, timestamp)
    self._label = (label, timestamp)  # Already decoded to string
    self._power = (power, timestamp)

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

    # Update state with timestamp
    import time

    self._color = (color, time.time())
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
get_power() -> bool
```

Get light power state (specific to light, not device).

Always fetches from device. Use the `power` property to access stored value.

This overrides Device.get_power() as it queries the light-specific power state (packet type 116/118) instead of device power (packet type 20/22).

| RETURNS | DESCRIPTION                                  |
| ------- | -------------------------------------------- |
| `bool`  | True if light is powered on, False otherwise |

| RAISES                    | DESCRIPTION                |
| ------------------------- | -------------------------- |
| `LifxDeviceNotFoundError` | If device is not connected |
| `LifxTimeoutError`        | If device does not respond |
| `LifxProtocolError`       | If response is invalid     |

Example

```python
is_on = await light.get_power()
print(f"Light power: {'ON' if is_on else 'OFF'}")
```

Source code in `src/lifx/devices/light.py`

````python
async def get_power(self) -> bool:
    """Get light power state (specific to light, not device).

    Always fetches from device. Use the `power` property to access stored value.

    This overrides Device.get_power() as it queries the light-specific
    power state (packet type 116/118) instead of device power (packet type 20/22).

    Returns:
        True if light is powered on, False otherwise

    Raises:
        LifxDeviceNotFoundError: If device is not connected
        LifxTimeoutError: If device does not respond
        LifxProtocolError: If response is invalid

    Example:
        ```python
        is_on = await light.get_power()
        print(f"Light power: {'ON' if is_on else 'OFF'}")
        ```
    """
    # Request automatically unpacks response
    state = await self.connection.request(packets.Light.GetPower())

    # Power level is uint16 (0 or 65535)
    is_on = state.level > 0

    import time

    self._power = (is_on, time.time())

    _LOGGER.debug(
        {
            "class": "Device",
            "method": "get_power",
            "action": "query",
            "reply": {"level": state.level},
        }
    )

    return is_on
````

##### set_power

```python
set_power(on: bool, duration: float = 0.0) -> None
```

Set light power state (specific to light, not device).

This overrides Device.set_power() as it uses the light-specific power packet (type 117) which supports transition duration.

| PARAMETER  | DESCRIPTION                                                                       |
| ---------- | --------------------------------------------------------------------------------- |
| `on`       | True to turn on, False to turn off **TYPE:** `bool`                               |
| `duration` | Transition duration in seconds (default 0.0) **TYPE:** `float` **DEFAULT:** `0.0` |

| RAISES                    | DESCRIPTION                |
| ------------------------- | -------------------------- |
| `LifxDeviceNotFoundError` | If device is not connected |
| `LifxTimeoutError`        | If device does not respond |

Example

```python
# Turn on instantly
await light.set_power(True)

# Fade off over 3 seconds
await light.set_power(False, duration=3.0)
```

Source code in `src/lifx/devices/light.py`

````python
async def set_power(self, on: bool, duration: float = 0.0) -> None:
    """Set light power state (specific to light, not device).

    This overrides Device.set_power() as it uses the light-specific
    power packet (type 117) which supports transition duration.

    Args:
        on: True to turn on, False to turn off
        duration: Transition duration in seconds (default 0.0)

    Raises:
        LifxDeviceNotFoundError: If device is not connected
        LifxTimeoutError: If device does not respond

    Example:
        ```python
        # Turn on instantly
        await light.set_power(True)

        # Fade off over 3 seconds
        await light.set_power(False, duration=3.0)
        ```
    """
    # Power level: 0 for off, 65535 for on
    level = 65535 if on else 0

    # Convert duration to milliseconds
    duration_ms = int(duration * 1000)

    # Request automatically handles acknowledgement
    await self.connection.request(
        packets.Light.SetPower(level=level, duration=duration_ms),
    )

    # Update state with timestamp
    import time

    self._power = (on, time.time())
    _LOGGER.debug(
        {
            "class": "Device",
            "method": "set_power",
            "action": "change",
            "values": {"level": level, "duration": duration_ms},
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

| ATTRIBUTE    | DESCRIPTION                                                                                                     |
| ------------ | --------------------------------------------------------------------------------------------------------------- |
| `hev_cycle`  | Get stored HEV cycle state with timestamp if available. **TYPE:** \`tuple[HevCycleState, float]                 |
| `hev_config` | Get stored HEV configuration with timestamp if available. **TYPE:** \`tuple[HevConfig, float]                   |
| `hev_result` | Get stored last HEV cycle result with timestamp if available. **TYPE:** \`tuple[LightLastHevCycleResult, float] |

Source code in `src/lifx/devices/hev.py`

```python
def __init__(self, *args, **kwargs) -> None:
    """Initialize HevLight with additional state attributes."""
    super().__init__(*args, **kwargs)
    # HEV-specific state storage
    self._hev_cycle: tuple[HevCycleState, float] | None = None
    self._hev_config: tuple[HevConfig, float] | None = None
    self._hev_result: tuple[LightLastHevCycleResult, float] | None = None
```

#### Attributes

##### hev_cycle

```python
hev_cycle: tuple[HevCycleState, float] | None
```

Get stored HEV cycle state with timestamp if available.

| RETURNS                       | DESCRIPTION |
| ----------------------------- | ----------- |
| \`tuple[HevCycleState, float] | None\`      |
| \`tuple[HevCycleState, float] | None\`      |

##### hev_config

```python
hev_config: tuple[HevConfig, float] | None
```

Get stored HEV configuration with timestamp if available.

| RETURNS                   | DESCRIPTION |
| ------------------------- | ----------- |
| \`tuple[HevConfig, float] | None\`      |
| \`tuple[HevConfig, float] | None\`      |

##### hev_result

```python
hev_result: tuple[LightLastHevCycleResult, float] | None
```

Get stored last HEV cycle result with timestamp if available.

| RETURNS                                 | DESCRIPTION |
| --------------------------------------- | ----------- |
| \`tuple[LightLastHevCycleResult, float] | None\`      |
| \`tuple[LightLastHevCycleResult, float] | None\`      |

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

    # Store state with timestamp
    import time

    self._hev_cycle = (cycle_state, time.time())

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

    # Invalidate state since it changed
    self._hev_cycle = None
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

    # Store state with timestamp
    import time

    self._hev_config = (config, time.time())

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

    # Update state with timestamp
    import time

    self._hev_config = (
        HevConfig(indication=indication, duration_s=duration_seconds),
        time.time(),
    )
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

    # Store state with timestamp
    import time

    self._hev_result = (state.result, time.time())

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

| ATTRIBUTE  | DESCRIPTION                                                                                 |
| ---------- | ------------------------------------------------------------------------------------------- |
| `infrared` | Get stored infrared brightness with timestamp if available. **TYPE:** \`tuple[float, float] |

Source code in `src/lifx/devices/infrared.py`

```python
def __init__(self, *args, **kwargs) -> None:
    """Initialize InfraredLight with additional state attributes."""
    super().__init__(*args, **kwargs)
    # Infrared-specific state storage
    self._infrared: tuple[float, float] | None = None
```

#### Attributes

##### infrared

```python
infrared: tuple[float, float] | None
```

Get stored infrared brightness with timestamp if available.

| RETURNS               | DESCRIPTION |
| --------------------- | ----------- |
| \`tuple[float, float] | None\`      |
| \`tuple[float, float] | None\`      |

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

    # Store state with timestamp
    import time

    self._infrared = (brightness, time.time())

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

    # Update state with timestamp
    import time

    self._infrared = (brightness, time.time())
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
| `set_color_zones`          | Set color for a range of zones.                                      |
| `set_extended_color_zones` | Set colors for multiple zones efficiently (up to 82 zones per call). |
| `get_multizone_effect`     | Get current multizone effect.                                        |
| `set_multizone_effect`     | Set multizone effect.                                                |
| `stop_effect`              | Stop any running multizone effect.                                   |
| `set_move_effect`          | Apply a moving effect that shifts colors along the strip.            |
| `apply_theme`              | Apply a theme across zones.                                          |

| ATTRIBUTE          | DESCRIPTION                                                                                 |
| ------------------ | ------------------------------------------------------------------------------------------- |
| `zone_count`       | Get stored zone count with timestamp if available. **TYPE:** \`tuple[int, float]            |
| `multizone_effect` | Get stored multizone effect with timestamp if available. **TYPE:** \`tuple\[MultiZoneEffect |
| `zones`            | Get stored zone colors with timestamp if available. **TYPE:** \`tuple\[list[HSBK], float\]  |

Source code in `src/lifx/devices/multizone.py`

```python
def __init__(self, *args, **kwargs) -> None:
    """Initialize MultiZoneLight with additional state attributes."""
    super().__init__(*args, **kwargs)
    # MultiZone-specific state storage
    self._zone_count: tuple[int, float] | None = None
    self._multizone_effect: tuple[MultiZoneEffect | None, float] | None = None
    # Zone colors - list of all zone colors with single timestamp
    # Updated whenever any zone query is performed
    self._zones: tuple[list[HSBK], float] | None = None
```

#### Attributes

##### zone_count

```python
zone_count: tuple[int, float] | None
```

Get stored zone count with timestamp if available.

| RETURNS             | DESCRIPTION |
| ------------------- | ----------- |
| \`tuple[int, float] | None\`      |
| \`tuple[int, float] | None\`      |

##### multizone_effect

```python
multizone_effect: tuple[MultiZoneEffect | None, float] | None
```

Get stored multizone effect with timestamp if available.

| RETURNS                  | DESCRIPTION   |
| ------------------------ | ------------- |
| \`tuple\[MultiZoneEffect | None, float\] |
| \`tuple\[MultiZoneEffect | None, float\] |

##### zones

```python
zones: tuple[list[HSBK], float] | None
```

Get stored zone colors with timestamp if available.

| RETURNS                      | DESCRIPTION |
| ---------------------------- | ----------- |
| \`tuple\[list[HSBK], float\] | None\`      |
| \`tuple\[list[HSBK], float\] | None\`      |

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
````

##### get_color_zones

```python
get_color_zones(start: int, end: int) -> list[HSBK]
```

Get colors for a range of zones using GetColorZones.

Always fetches from device. Use `zones` property to access stored values.

| PARAMETER | DESCRIPTION                                  |
| --------- | -------------------------------------------- |
| `start`   | Start zone index (inclusive) **TYPE:** `int` |
| `end`     | End zone index (inclusive) **TYPE:** `int`   |

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
# Get colors for first 10 zones
colors = await light.get_color_zones(0, 9)
for i, color in enumerate(colors):
    print(f"Zone {i}: {color}")
```

Source code in `src/lifx/devices/multizone.py`

````python
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
````

##### get_extended_color_zones

```python
get_extended_color_zones(start: int, end: int) -> list[HSBK]
```

Get colors for a range of zones using GetExtendedColorZones.

Always fetches from device. Use `zones` property to access stored values.

| PARAMETER | DESCRIPTION                                  |
| --------- | -------------------------------------------- |
| `start`   | Start zone index (inclusive) **TYPE:** `int` |
| `end`     | End zone index (inclusive) **TYPE:** `int`   |

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
# Get colors for first 10 zones
colors = await light.get_color_zones(0, 9)
for i, color in enumerate(colors):
    print(f"Zone {i}: {color}")
```

Source code in `src/lifx/devices/multizone.py`

````python
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

## Tile Device

The `TileDevice` class controls LIFX tile grids with 2D zone control.

### TileDevice

```python
TileDevice(*args, **kwargs)
```

Bases: `Light`

LIFX Tile device with grid control.

Extends the Light class with tile-specific functionality:

- Tile chain discovery and information
- Individual tile grid color control
- Tile effects (morph, flame, sky)

Example

```python
tile = TileDevice(serial="d073d5123456", ip="192.168.1.100")

async with tile:
    # Get tile chain information
    chain = await tile.get_tile_chain()
    print(f"Device has {len(chain)} tiles")

    # Get colors from first tile
    colors = await tile.get_tile_colors(tile_index=0)

    # Set entire first tile to red
    red = HSBK.from_rgb(255, 0, 0)
    await tile.set_tile_colors(
        tile_index=0, colors=[[red] * 8 for _ in range(8)]
    )

    # Apply a flame effect
    await tile.set_flame_effect(speed=5.0)
```

Using the simplified connect method:

```python
async with await TileDevice.from_ip(ip="192.168.1.100") as light:
    await tile.set_flame_effect(speed=5.0)
```

| METHOD              | DESCRIPTION                                                    |
| ------------------- | -------------------------------------------------------------- |
| `get_tile_chain`    | Get information about all tiles in the chain.                  |
| `get_tile_count`    | Get the number of tiles in the chain.                          |
| `get_tile_colors`   | Get colors from a tile.                                        |
| `set_tile_colors`   | Set colors on a tile.                                          |
| `get_tile_effect`   | Get current tile effect.                                       |
| `set_tile_effect`   | Set tile effect.                                               |
| `stop_effect`       | Stop any running tile effect.                                  |
| `copy_frame_buffer` | Copy a rectangular region from one frame buffer to another.    |
| `set_morph_effect`  | Apply a morph effect that transitions through a color palette. |
| `set_flame_effect`  | Apply a flame effect.                                          |
| `apply_theme`       | Apply a theme to this tile device.                             |

| ATTRIBUTE     | DESCRIPTION                                                                                           |
| ------------- | ----------------------------------------------------------------------------------------------------- |
| `tile_chain`  | Get stored tile chain if available. **TYPE:** \`tuple\[list[TileInfo], float\]                        |
| `tile_count`  | Get stored tile count with timestamp if available. **TYPE:** \`tuple[int, float]                      |
| `tile_effect` | Get stored tile effect if available. **TYPE:** \`tuple\[TileEffect                                    |
| `tile_colors` | Get stored tile colors with timestamp if available. **TYPE:** \`tuple\[dict[int, TileColors], float\] |

Source code in `src/lifx/devices/tile.py`

```python
def __init__(self, *args, **kwargs) -> None:
    """Initialize TileDevice with additional state attributes."""
    super().__init__(*args, **kwargs)
    # Tile-specific state storage
    self._tile_chain: tuple[list[TileInfo], float] | None = None
    self._tile_effect: tuple[TileEffect | None, float] | None = None
    # Tile colors: dict indexed by tile_index with TileColors for each tile
    # Structure: dict[tile_index] -> TileColors(colors, width, height)
    self._tile_colors: tuple[dict[int, TileColors], float] | None = None
```

#### Attributes

##### tile_chain

```python
tile_chain: tuple[list[TileInfo], float] | None
```

Get stored tile chain if available.

| RETURNS                          | DESCRIPTION |
| -------------------------------- | ----------- |
| \`tuple\[list[TileInfo], float\] | None\`      |

##### tile_count

```python
tile_count: tuple[int, float] | None
```

Get stored tile count with timestamp if available.

| RETURNS             | DESCRIPTION |
| ------------------- | ----------- |
| \`tuple[int, float] | None\`      |
| \`tuple[int, float] | None\`      |

##### tile_effect

```python
tile_effect: tuple[TileEffect | None, float] | None
```

Get stored tile effect if available.

| RETURNS             | DESCRIPTION   |
| ------------------- | ------------- |
| \`tuple\[TileEffect | None, float\] |

##### tile_colors

```python
tile_colors: tuple[dict[int, TileColors], float] | None
```

Get stored tile colors with timestamp if available.

| RETURNS                                 | DESCRIPTION |
| --------------------------------------- | ----------- |
| \`tuple\[dict[int, TileColors], float\] | None\`      |
| \`tuple\[dict[int, TileColors], float\] | None\`      |
| \`tuple\[dict[int, TileColors], float\] | None\`      |
| \`tuple\[dict[int, TileColors], float\] | None\`      |

Example

```python
if tile.tile_colors:
    colors_dict, timestamp = tile.tile_colors
    tile_0 = colors_dict[0]
    # Access flat list: tile_0.colors
    # Get dimensions: tile_0.width, tile_0.height
    # Get 2D array: tile_0.to_2d()
    # Get specific color: tile_0.get_color(x, y)
```

#### Functions

##### get_tile_chain

```python
get_tile_chain() -> list[TileInfo]
```

Get information about all tiles in the chain.

Always fetches from device. Use the `tile_chain` property to access stored value.

| RETURNS          | DESCRIPTION                            |
| ---------------- | -------------------------------------- |
| `list[TileInfo]` | List of TileInfo objects, one per tile |

| RAISES                    | DESCRIPTION                |
| ------------------------- | -------------------------- |
| `LifxDeviceNotFoundError` | If device is not connected |
| `LifxTimeoutError`        | If device does not respond |
| `LifxProtocolError`       | If response is invalid     |

Example

```python
chain = await tile.get_tile_chain()
for i, tile_info in enumerate(chain):
    print(f"Tile {i}: {tile_info.width}x{tile_info.height}")
```

Source code in `src/lifx/devices/tile.py`

````python
async def get_tile_chain(self) -> list[TileInfo]:
    """Get information about all tiles in the chain.

    Always fetches from device.
    Use the `tile_chain` property to access stored value.

    Returns:
        List of TileInfo objects, one per tile

    Raises:
        LifxDeviceNotFoundError: If device is not connected
        LifxTimeoutError: If device does not respond
        LifxProtocolError: If response is invalid

    Example:
        ```python
        chain = await tile.get_tile_chain()
        for i, tile_info in enumerate(chain):
            print(f"Tile {i}: {tile_info.width}x{tile_info.height}")
        ```
    """
    # Request automatically unpacks response
    state = await self.connection.request(packets.Tile.GetDeviceChain())

    # Convert protocol TileDevice objects to TileInfo
    tiles = [
        TileInfo.from_protocol(tile_device)
        for tile_device in state.tile_devices[: state.tile_devices_count]
    ]

    import time

    self._tile_chain = (tiles, time.time())

    _LOGGER.debug(
        {
            "class": "Device",
            "method": "get_tile_chain",
            "action": "query",
            "reply": {
                "tile_devices_count": state.tile_devices_count,
                "tiles": [
                    {
                        "width": tile.width,
                        "height": tile.height,
                        "device_version_vendor": tile.device_version_vendor,
                        "device_version_product": tile.device_version_product,
                        "firmware_version_major": tile.firmware_version_major,
                        "firmware_version_minor": tile.firmware_version_minor,
                    }
                    for tile in tiles
                ],
            },
        }
    )

    return tiles
````

##### get_tile_count

```python
get_tile_count() -> int
```

Get the number of tiles in the chain.

Always fetches from device. Use the `tile_count` property to access stored value.

| RETURNS | DESCRIPTION     |
| ------- | --------------- |
| `int`   | Number of tiles |

Example

```python
count = await tile.get_tile_count()
print(f"Device has {count} tiles")
```

Source code in `src/lifx/devices/tile.py`

````python
async def get_tile_count(self) -> int:
    """Get the number of tiles in the chain.

    Always fetches from device.
    Use the `tile_count` property to access stored value.

    Returns:
        Number of tiles

    Example:
        ```python
        count = await tile.get_tile_count()
        print(f"Device has {count} tiles")
        ```
    """
    chain = await self.get_tile_chain()
    count = len(chain)

    _LOGGER.debug(
        {
            "class": "Device",
            "method": "get_tile_count",
            "action": "query",
            "reply": {
                "count": count,
            },
        }
    )

    return count
````

##### get_tile_colors

```python
get_tile_colors(
    tile_index: int,
    x: int = 0,
    y: int = 0,
    width: int | None = None,
    height: int | None = None,
) -> list[list[HSBK]]
```

Get colors from a tile.

Always fetches from device. Use the `tile_colors` property to access stored value.

Returns a 2D array of colors representing the zones. For tiles with >64 zones, multiple Get64 requests are sent sequentially.

| PARAMETER    | DESCRIPTION                                                        |
| ------------ | ------------------------------------------------------------------ |
| `tile_index` | Index of tile in chain (0-based) **TYPE:** `int`                   |
| `x`          | Starting X coordinate (default 0) **TYPE:** `int` **DEFAULT:** `0` |
| `y`          | Starting Y coordinate (default 0) **TYPE:** `int` **DEFAULT:** `0` |
| `width`      | Rectangle width in zones (default: tile width) **TYPE:** \`int     |
| `height`     | Rectangle height in zones (default: tile height) **TYPE:** \`int   |

| RETURNS            | DESCRIPTION            |
| ------------------ | ---------------------- |
| `list[list[HSBK]]` | 2D list of HSBK colors |

| RAISES                    | DESCRIPTION                             |
| ------------------------- | --------------------------------------- |
| `ValueError`              | If tile_index or dimensions are invalid |
| `LifxDeviceNotFoundError` | If device is not connected              |
| `LifxTimeoutError`        | If device does not respond              |
| `LifxProtocolError`       | If response is invalid                  |

Example

```python
# Get all colors from first tile
colors = await tile.get_tile_colors(0)
print(f"Top-left zone: {colors[0][0]}")

# Get colors from specific rectangle
colors = await tile.get_tile_colors(0, x=2, y=2, width=4, height=4)
```

Source code in `src/lifx/devices/tile.py`

````python
async def get_tile_colors(
    self,
    tile_index: int,
    x: int = 0,
    y: int = 0,
    width: int | None = None,
    height: int | None = None,
) -> list[list[HSBK]]:
    """Get colors from a tile.

    Always fetches from device.
    Use the `tile_colors` property to access stored value.

    Returns a 2D array of colors representing the zones.
    For tiles with >64 zones, multiple Get64 requests are sent sequentially.

    Args:
        tile_index: Index of tile in chain (0-based)
        x: Starting X coordinate (default 0)
        y: Starting Y coordinate (default 0)
        width: Rectangle width in zones (default: tile width)
        height: Rectangle height in zones (default: tile height)

    Returns:
        2D list of HSBK colors

    Raises:
        ValueError: If tile_index or dimensions are invalid
        LifxDeviceNotFoundError: If device is not connected
        LifxTimeoutError: If device does not respond
        LifxProtocolError: If response is invalid

    Example:
        ```python
        # Get all colors from first tile
        colors = await tile.get_tile_colors(0)
        print(f"Top-left zone: {colors[0][0]}")

        # Get colors from specific rectangle
        colors = await tile.get_tile_colors(0, x=2, y=2, width=4, height=4)
        ```
    """
    if tile_index < 0:
        raise ValueError(f"Invalid tile index: {tile_index}")
    if x < 0 or y < 0:
        raise ValueError(f"Invalid coordinates: x={x}, y={y}")

    # Get tile info to determine dimensions
    chain = await self.get_tile_chain()
    if tile_index >= len(chain):
        raise ValueError(
            f"Tile index {tile_index} out of range (chain has {len(chain)} tiles)"
        )

    tile_info = chain[tile_index]

    # Default to full tile if dimensions not specified
    if width is None:
        width = tile_info.width - x
    if height is None:
        height = tile_info.height - y

    # Validate dimensions
    if width <= 0 or height <= 0:
        raise ValueError(f"Invalid dimensions: width={width}, height={height}")
    if x + width > tile_info.width or y + height > tile_info.height:
        raise ValueError(
            f"Rectangle exceeds tile dimensions ({x},{y},{width},{height}) "
            f"vs ({tile_info.width}x{tile_info.height})"
        )

    total_zones = width * height

    if total_zones <= 64:
        # Single Get64 request sufficient
        state = await self.connection.request(
            packets.Tile.Get64(
                tile_index=tile_index,
                length=1,
                rect=TileBufferRect(fb_index=0, x=x, y=y, width=width),
            ),
        )

        # Convert colors from protocol HSBK to HSBK
        colors_flat = [
            HSBK.from_protocol(color) for color in state.colors[:total_zones]
        ]
    else:
        # Multiple Get64 requests needed
        # Split into chunks by rows, taking as many rows as fit in 64 zones
        colors_flat: list[HSBK] = []
        current_y = y

        while current_y < y + height:
            # Calculate how many rows we can fetch in this chunk (max 64 zones)
            rows_in_chunk = min((64 // width), (y + height - current_y))
            if rows_in_chunk == 0:
                rows_in_chunk = 1  # Always fetch at least 1 row

            # Send Get64 request for this chunk
            state = await self.connection.request(
                packets.Tile.Get64(
                    tile_index=tile_index,
                    length=1,
                    rect=TileBufferRect(fb_index=0, x=x, y=current_y, width=width),
                ),
            )

            # Extract colors for this chunk
            zones_in_chunk = width * rows_in_chunk
            chunk_colors = [
                HSBK.from_protocol(color) for color in state.colors[:zones_in_chunk]
            ]
            colors_flat.extend(chunk_colors)

            current_y += rows_in_chunk

    # Convert flat list to 2D array [y][x]
    colors_2d: list[list[HSBK]] = []
    for row_idx in range(height):
        row: list[HSBK] = []
        for col_idx in range(width):
            index = row_idx * width + col_idx
            if index < len(colors_flat):
                row.append(colors_flat[index])
            else:
                # Pad with black if we don't have enough colors
                row.append(HSBK(0, 0, 0, 3500))
        colors_2d.append(row)

    # Update tile colors with fetched data
    import time

    timestamp = time.time()

    # Get tile chain to know dimensions
    if self._tile_chain is None:
        chain = await self.get_tile_chain()
    else:
        chain, _ = self._tile_chain

    # Get tile info for this specific tile
    tile_info = chain[tile_index]

    # Initialize or get existing colors dict
    if self._tile_colors is None:
        tiles_colors_dict = {}
    else:
        tiles_colors_dict, _ = self._tile_colors

    # Get or create TileColors for this tile
    if tile_index not in tiles_colors_dict:
        # Create new TileColors with default black colors
        num_zones = tile_info.width * tile_info.height
        default_colors = [HSBK(0, 0, 0, 3500)] * num_zones
        tiles_colors_dict[tile_index] = TileColors(
            colors=default_colors, width=tile_info.width, height=tile_info.height
        )

    tile_colors = tiles_colors_dict[tile_index]

    # Update the specific tile region with fetched colors
    for row_idx in range(height):
        for col_idx in range(width):
            tile_x = x + col_idx
            tile_y = y + row_idx
            if tile_y < tile_colors.height and tile_x < tile_colors.width:
                tile_colors.set_color(tile_x, tile_y, colors_2d[row_idx][col_idx])

    # Store updated colors with new timestamp
    self._tile_colors = (tiles_colors_dict, timestamp)

    _LOGGER.debug(
        {
            "class": "Device",
            "method": "get_tile_colors",
            "action": "query",
            "reply": {
                "tile_index": tile_index,
                "x": x,
                "y": y,
                "width": width,
                "height": height,
                "total_zones": total_zones,
            },
        }
    )

    return colors_2d
````

##### set_tile_colors

```python
set_tile_colors(
    tile_index: int,
    colors: list[list[HSBK]],
    x: int = 0,
    y: int = 0,
    duration: float = 0.0,
) -> None
```

Set colors on a tile.

For tiles with >64 zones, multiple Set64 requests are sent to frame buffer 1, then CopyFrameBuffer is used to atomically copy to frame buffer 0 with the specified duration. This eliminates flicker during multi-packet updates.

If the device is powered off, colors are set instantly (duration=0) and then the device is powered on with the specified duration for a smooth visual effect.

| PARAMETER    | DESCRIPTION                                                                       |
| ------------ | --------------------------------------------------------------------------------- |
| `tile_index` | Index of tile in chain (0-based) **TYPE:** `int`                                  |
| `colors`     | 2D list of HSBK colors **TYPE:** `list[list[HSBK]]`                               |
| `x`          | Starting X coordinate on tile (default 0) **TYPE:** `int` **DEFAULT:** `0`        |
| `y`          | Starting Y coordinate on tile (default 0) **TYPE:** `int` **DEFAULT:** `0`        |
| `duration`   | Transition duration in seconds (default 0.0) **TYPE:** `float` **DEFAULT:** `0.0` |

| RAISES                    | DESCRIPTION                |
| ------------------------- | -------------------------- |
| `ValueError`              | If parameters are invalid  |
| `LifxDeviceNotFoundError` | If device is not connected |
| `LifxTimeoutError`        | If device does not respond |

Example

```python
# Set entire 8x8 tile to red
red = HSBK.from_rgb(255, 0, 0)
colors = [[red] * 8 for _ in range(8)]
await tile.set_tile_colors(0, colors)

# Set a 4x4 area starting at (2, 2) with transition
blue = HSBK.from_rgb(0, 0, 255)
colors = [[blue] * 4 for _ in range(4)]
await tile.set_tile_colors(0, colors, x=2, y=2, duration=1.0)

# Set entire 16x8 wide tile with smooth transition
colors = [[HSBK.from_rgb(255, 0, 0)] * 16 for _ in range(8)]
await tile.set_tile_colors(0, colors, duration=2.0)
```

Source code in `src/lifx/devices/tile.py`

````python
async def set_tile_colors(
    self,
    tile_index: int,
    colors: list[list[HSBK]],
    x: int = 0,
    y: int = 0,
    duration: float = 0.0,
) -> None:
    """Set colors on a tile.

    For tiles with >64 zones, multiple Set64 requests are sent to frame buffer 1,
    then CopyFrameBuffer is used to atomically copy to frame buffer 0 with the
    specified duration. This eliminates flicker during multi-packet updates.

    If the device is powered off, colors are set instantly (duration=0) and then
    the device is powered on with the specified duration for a smooth visual effect.

    Args:
        tile_index: Index of tile in chain (0-based)
        colors: 2D list of HSBK colors
        x: Starting X coordinate on tile (default 0)
        y: Starting Y coordinate on tile (default 0)
        duration: Transition duration in seconds (default 0.0)

    Raises:
        ValueError: If parameters are invalid
        LifxDeviceNotFoundError: If device is not connected
        LifxTimeoutError: If device does not respond

    Example:
        ```python
        # Set entire 8x8 tile to red
        red = HSBK.from_rgb(255, 0, 0)
        colors = [[red] * 8 for _ in range(8)]
        await tile.set_tile_colors(0, colors)

        # Set a 4x4 area starting at (2, 2) with transition
        blue = HSBK.from_rgb(0, 0, 255)
        colors = [[blue] * 4 for _ in range(4)]
        await tile.set_tile_colors(0, colors, x=2, y=2, duration=1.0)

        # Set entire 16x8 wide tile with smooth transition
        colors = [[HSBK.from_rgb(255, 0, 0)] * 16 for _ in range(8)]
        await tile.set_tile_colors(0, colors, duration=2.0)
        ```
    """
    if tile_index < 0:
        raise ValueError(f"Invalid tile index: {tile_index}")
    if x < 0 or y < 0:
        raise ValueError(f"Invalid coordinates: x={x}, y={y}")
    if not colors or not colors[0]:
        raise ValueError("Colors array cannot be empty")

    height = len(colors)
    width = len(colors[0])

    # Validate that all rows have the same width
    for row in colors:
        if len(row) != width:
            raise ValueError("All rows in colors array must have the same width")

    # Flatten colors to 1D array
    colors_flat: list[HSBK] = []
    for row in colors:
        colors_flat.extend(row)

    total_zones = width * height

    # Check power state to optimize duration handling
    # If device is off, set colors instantly then power on with duration
    # Use stored power state if available, otherwise fetch
    power_tuple = self.power
    if power_tuple is not None:
        is_powered_on, _ = power_tuple
    else:
        is_powered_on = await self.get_power()

    # Convert duration to milliseconds
    duration_ms = int(duration * 1000)

    # Apply duration to colors only if device is already on
    color_duration_ms = duration_ms if is_powered_on else 0

    if total_zones <= 64:
        # Single Set64 request sufficient - write directly to visible frame buffer 0
        # Pad to 64 colors
        protocol_colors = [color.to_protocol() for color in colors_flat]
        while len(protocol_colors) < 64:
            protocol_colors.append(HSBK(0, 0, 0, 3500).to_protocol())

        await self.connection.request(
            packets.Tile.Set64(
                tile_index=tile_index,
                length=1,
                rect=TileBufferRect(fb_index=0, x=x, y=y, width=width),
                duration=color_duration_ms,
                colors=protocol_colors,
            ),
        )
    else:
        # Multiple Set64 requests needed for >64 zones
        # Write to buffer 1, then copy to buffer 0 atomically
        current_y = y
        flat_index = 0

        while flat_index < len(colors_flat):
            # Calculate how many rows we can write in this chunk (max 64 zones)
            rows_in_chunk = min((64 // width), (y + height - current_y))
            if rows_in_chunk == 0:
                rows_in_chunk = 1  # Always write at least 1 row

            # Extract colors for this chunk
            zones_in_chunk = width * rows_in_chunk
            chunk_colors = colors_flat[flat_index : flat_index + zones_in_chunk]

            # Pad to 64 colors
            protocol_colors = [color.to_protocol() for color in chunk_colors]
            while len(protocol_colors) < 64:
                protocol_colors.append(HSBK(0, 0, 0, 3500).to_protocol())

            # Write to frame buffer 1 (invisible) with no duration
            await self.connection.request(
                packets.Tile.Set64(
                    tile_index=tile_index,
                    length=1,
                    rect=TileBufferRect(fb_index=1, x=x, y=current_y, width=width),
                    duration=0,
                    colors=protocol_colors,
                ),
            )

            flat_index += zones_in_chunk
            current_y += rows_in_chunk

        # Copy from buffer 1 to buffer 0 with transition duration
        copy_duration = duration if is_powered_on else 0.0
        await self.copy_frame_buffer(
            tile_index=tile_index,
            src_fb_index=1,
            dst_fb_index=0,
            src_x=x,
            src_y=y,
            dst_x=x,
            dst_y=y,
            width=width,
            height=height,
            duration=copy_duration,
        )

    # Update tile colors with the values we just set
    import time

    timestamp = time.time()

    # Get tile chain to know dimensions
    if self._tile_chain is None:
        chain = await self.get_tile_chain()
    else:
        chain, _ = self._tile_chain

    # Get tile info for this specific tile
    tile_info = chain[tile_index]

    # Initialize or get existing colors dict
    if self._tile_colors is None:
        tiles_colors_dict = {}
    else:
        tiles_colors_dict, _ = self._tile_colors

    # Get or create TileColors for this tile
    if tile_index not in tiles_colors_dict:
        # Create new TileColors with default black colors
        num_zones = tile_info.width * tile_info.height
        default_colors = [HSBK(0, 0, 0, 3500)] * num_zones
        tiles_colors_dict[tile_index] = TileColors(
            colors=default_colors, width=tile_info.width, height=tile_info.height
        )

    tile_colors = tiles_colors_dict[tile_index]

    # Update the specific tile region with colors we just set
    for row_idx in range(height):
        for col_idx in range(width):
            tile_x = x + col_idx
            tile_y = y + row_idx
            if tile_y < tile_colors.height and tile_x < tile_colors.width:
                tile_colors.set_color(tile_x, tile_y, colors[row_idx][col_idx])

    # Store updated colors with new timestamp
    self._tile_colors = (tiles_colors_dict, timestamp)

    _LOGGER.debug(
        {
            "class": "Device",
            "method": "set_tile_colors",
            "action": "change",
            "values": {
                "tile_index": tile_index,
                "x": x,
                "y": y,
                "width": width,
                "height": height,
                "total_zones": total_zones,
                "duration": duration,
            },
        }
    )

    # If device was off, power it on with the specified duration
    if not is_powered_on and duration > 0:
        await self.set_power(True, duration=duration)
````

##### get_tile_effect

```python
get_tile_effect() -> TileEffect | None
```

Get current tile effect.

Always fetches from device. Use the `tile_effect` property to access stored value.

| RETURNS      | DESCRIPTION |
| ------------ | ----------- |
| \`TileEffect | None\`      |

| RAISES                    | DESCRIPTION                |
| ------------------------- | -------------------------- |
| `LifxDeviceNotFoundError` | If device is not connected |
| `LifxTimeoutError`        | If device does not respond |
| `LifxProtocolError`       | If response is invalid     |

Example

```python
effect = await tile.get_tile_effect()
if effect:
    print(f"Effect: {effect.effect_type}, Speed: {effect.speed}ms")
```

Source code in `src/lifx/devices/tile.py`

````python
async def get_tile_effect(self) -> TileEffect | None:
    """Get current tile effect.

    Always fetches from device.
    Use the `tile_effect` property to access stored value.

    Returns:
        TileEffect if an effect is active, None if no effect

    Raises:
        LifxDeviceNotFoundError: If device is not connected
        LifxTimeoutError: If device does not respond
        LifxProtocolError: If response is invalid

    Example:
        ```python
        effect = await tile.get_tile_effect()
        if effect:
            print(f"Effect: {effect.effect_type}, Speed: {effect.speed}ms")
        ```
    """
    # Request automatically unpacks response
    state = await self.connection.request(packets.Tile.GetEffect())

    settings = state.settings
    effect_type = settings.effect_type

    # Extract parameters from the settings parameter field
    parameters = [
        int(settings.parameter.sky_type),
        settings.parameter.cloud_saturation_min,
        settings.parameter.cloud_saturation_max,
    ]

    # Convert palette from protocol HSBK to HSBK
    palette = [
        HSBK.from_protocol(color)
        for color in settings.palette[: settings.palette_count]
    ]

    if effect_type == TileEffectType.OFF:
        result = None
    else:
        result = TileEffect(
            effect_type=effect_type,
            speed=settings.speed,
            duration=settings.duration,
            palette=palette,
            parameters=parameters,
        )

    import time

    self._tile_effect = (result, time.time())

    _LOGGER.debug(
        {
            "class": "Device",
            "method": "get_tile_effect",
            "action": "query",
            "reply": {
                "effect_type": effect_type.name,
                "speed": settings.speed,
                "duration": settings.duration,
                "palette_count": settings.palette_count,
                "parameters": parameters,
            },
        }
    )

    return result
````

##### set_tile_effect

```python
set_tile_effect(effect: TileEffect) -> None
```

Set tile effect.

| PARAMETER | DESCRIPTION                                      |
| --------- | ------------------------------------------------ |
| `effect`  | Tile effect configuration **TYPE:** `TileEffect` |

| RAISES                    | DESCRIPTION                    |
| ------------------------- | ------------------------------ |
| `ValueError`              | If palette has too many colors |
| `LifxDeviceNotFoundError` | If device is not connected     |
| `LifxTimeoutError`        | If device does not respond     |

Example

```python
# Apply a morph effect with rainbow palette
palette = [
    HSBK(0, 1.0, 1.0, 3500),  # Red
    HSBK(60, 1.0, 1.0, 3500),  # Yellow
    HSBK(120, 1.0, 1.0, 3500),  # Green
    HSBK(240, 1.0, 1.0, 3500),  # Blue
]
effect = TileEffect(
    effect_type=TileEffectType.MORPH,
    speed=5000,
    palette=palette,
)
await tile.set_tile_effect(effect)
```

Source code in `src/lifx/devices/tile.py`

````python
async def set_tile_effect(self, effect: TileEffect) -> None:
    """Set tile effect.

    Args:
        effect: Tile effect configuration

    Raises:
        ValueError: If palette has too many colors
        LifxDeviceNotFoundError: If device is not connected
        LifxTimeoutError: If device does not respond

    Example:
        ```python
        # Apply a morph effect with rainbow palette
        palette = [
            HSBK(0, 1.0, 1.0, 3500),  # Red
            HSBK(60, 1.0, 1.0, 3500),  # Yellow
            HSBK(120, 1.0, 1.0, 3500),  # Green
            HSBK(240, 1.0, 1.0, 3500),  # Blue
        ]
        effect = TileEffect(
            effect_type=TileEffectType.MORPH,
            speed=5000,
            palette=palette,
        )
        await tile.set_tile_effect(effect)
        ```
    """
    palette = effect.palette or [HSBK(0, 0, 1.0, 3500)]
    if len(palette) > 16:
        raise ValueError(f"Palette too large: {len(palette)} colors (max 16)")

    # Convert palette to protocol HSBK and pad to 16
    protocol_palette = [color.to_protocol() for color in palette]

    while len(protocol_palette) < 16:
        protocol_palette.append(HSBK(0, 0, 0, 3500).to_protocol())

    # Ensure parameters list is 3 elements (sky_type, cloud_sat_min, cloud_sat_max)
    parameters = effect.parameters or [0] * 3
    if len(parameters) < 3:
        parameters.extend([0] * (3 - len(parameters)))
    parameters = parameters[:3]

    # Request automatically handles acknowledgement
    await self.connection.request(
        packets.Tile.SetEffect(
            settings=TileEffectSettings(
                instanceid=0,  # 0 for new effect
                effect_type=effect.effect_type,
                speed=effect.speed,
                duration=effect.duration,
                parameter=TileEffectParameter(
                    sky_type=TileEffectSkyType(value=parameters[0]),
                    cloud_saturation_min=parameters[1],
                    cloud_saturation_max=parameters[2],
                ),
                palette_count=len(palette),
                palette=protocol_palette,
            ),
        ),
    )

    # Update state attribute
    import time

    result = effect if effect.effect_type != TileEffectType.OFF else None
    self._tile_effect = (result, time.time())

    _LOGGER.debug(
        {
            "class": "Device",
            "method": "set_tile_effect",
            "action": "change",
            "values": {
                "effect_type": effect.effect_type.name,
                "speed": effect.speed,
                "duration": effect.duration,
                "palette_count": len(palette),
                "parameters": parameters,
            },
        }
    )
````

##### stop_effect

```python
stop_effect() -> None
```

Stop any running tile effect.

Example

```python
await tile.stop_effect()
```

Source code in `src/lifx/devices/tile.py`

````python
async def stop_effect(self) -> None:
    """Stop any running tile effect.

    Example:
        ```python
        await tile.stop_effect()
        ```
    """
    await self.set_tile_effect(
        TileEffect(
            effect_type=TileEffectType.OFF,
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

##### copy_frame_buffer

```python
copy_frame_buffer(
    tile_index: int,
    src_fb_index: int = 0,
    dst_fb_index: int = 0,
    src_x: int = 0,
    src_y: int = 0,
    dst_x: int = 0,
    dst_y: int = 0,
    width: int = 8,
    height: int = 8,
    duration: float = 0.0,
) -> None
```

Copy a rectangular region from one frame buffer to another.

This allows copying pixel data between frame buffers or within the same frame buffer on a tile. Useful for double-buffering effects or moving pixel regions.

| PARAMETER      | DESCRIPTION                                                                       |
| -------------- | --------------------------------------------------------------------------------- |
| `tile_index`   | Index of tile in chain (0-based) **TYPE:** `int`                                  |
| `src_fb_index` | Source frame buffer index (default 0) **TYPE:** `int` **DEFAULT:** `0`            |
| `dst_fb_index` | Destination frame buffer index (default 0) **TYPE:** `int` **DEFAULT:** `0`       |
| `src_x`        | Source rectangle X coordinate (default 0) **TYPE:** `int` **DEFAULT:** `0`        |
| `src_y`        | Source rectangle Y coordinate (default 0) **TYPE:** `int` **DEFAULT:** `0`        |
| `dst_x`        | Destination rectangle X coordinate (default 0) **TYPE:** `int` **DEFAULT:** `0`   |
| `dst_y`        | Destination rectangle Y coordinate (default 0) **TYPE:** `int` **DEFAULT:** `0`   |
| `width`        | Rectangle width in zones (default 8) **TYPE:** `int` **DEFAULT:** `8`             |
| `height`       | Rectangle height in zones (default 8) **TYPE:** `int` **DEFAULT:** `8`            |
| `duration`     | Transition duration in seconds (default 0.0) **TYPE:** `float` **DEFAULT:** `0.0` |

| RAISES                    | DESCRIPTION                               |
| ------------------------- | ----------------------------------------- |
| `ValueError`              | If parameters are invalid or out of range |
| `LifxDeviceNotFoundError` | If device is not connected                |
| `LifxTimeoutError`        | If device does not respond                |

Example

```python
# Copy entire tile from frame buffer 0 to frame buffer 1
await tile.copy_frame_buffer(tile_index=0, src_fb_index=0, dst_fb_index=1)

# Copy a 4x4 region from (0,0) to (2,2) within same buffer with transition
await tile.copy_frame_buffer(
    tile_index=0,
    src_x=0,
    src_y=0,
    dst_x=2,
    dst_y=2,
    width=4,
    height=4,
    duration=1.0,
)
```

Source code in `src/lifx/devices/tile.py`

````python
async def copy_frame_buffer(
    self,
    tile_index: int,
    src_fb_index: int = 0,
    dst_fb_index: int = 0,
    src_x: int = 0,
    src_y: int = 0,
    dst_x: int = 0,
    dst_y: int = 0,
    width: int = 8,
    height: int = 8,
    duration: float = 0.0,
) -> None:
    """Copy a rectangular region from one frame buffer to another.

    This allows copying pixel data between frame buffers or within the same
    frame buffer on a tile. Useful for double-buffering effects or moving
    pixel regions.

    Args:
        tile_index: Index of tile in chain (0-based)
        src_fb_index: Source frame buffer index (default 0)
        dst_fb_index: Destination frame buffer index (default 0)
        src_x: Source rectangle X coordinate (default 0)
        src_y: Source rectangle Y coordinate (default 0)
        dst_x: Destination rectangle X coordinate (default 0)
        dst_y: Destination rectangle Y coordinate (default 0)
        width: Rectangle width in zones (default 8)
        height: Rectangle height in zones (default 8)
        duration: Transition duration in seconds (default 0.0)

    Raises:
        ValueError: If parameters are invalid or out of range
        LifxDeviceNotFoundError: If device is not connected
        LifxTimeoutError: If device does not respond

    Example:
        ```python
        # Copy entire tile from frame buffer 0 to frame buffer 1
        await tile.copy_frame_buffer(tile_index=0, src_fb_index=0, dst_fb_index=1)

        # Copy a 4x4 region from (0,0) to (2,2) within same buffer with transition
        await tile.copy_frame_buffer(
            tile_index=0,
            src_x=0,
            src_y=0,
            dst_x=2,
            dst_y=2,
            width=4,
            height=4,
            duration=1.0,
        )
        ```
    """
    if tile_index < 0:
        raise ValueError(f"Invalid tile index: {tile_index}")
    if src_fb_index < 0 or dst_fb_index < 0:
        raise ValueError(
            f"Invalid frame buffer indices: src={src_fb_index}, dst={dst_fb_index}"
        )
    if src_x < 0 or src_y < 0 or dst_x < 0 or dst_y < 0:
        raise ValueError(
            f"Invalid coordinates: src=({src_x},{src_y}), dst=({dst_x},{dst_y})"
        )
    if width <= 0 or height <= 0:
        raise ValueError(f"Invalid dimensions: {width}x{height}")

    # Get tile info to validate dimensions
    chain = await self.get_tile_chain()
    if tile_index >= len(chain):
        raise ValueError(
            f"Tile index {tile_index} out of range (chain has {len(chain)} tiles)"
        )

    tile_info = chain[tile_index]

    # Validate source rectangle
    if src_x + width > tile_info.width or src_y + height > tile_info.height:
        raise ValueError(
            f"Source rectangle ({src_x},{src_y},{width},{height}) "
            f"exceeds tile dimensions ({tile_info.width}x{tile_info.height})"
        )

    # Validate destination rectangle
    if dst_x + width > tile_info.width or dst_y + height > tile_info.height:
        raise ValueError(
            f"Destination rectangle ({dst_x},{dst_y},{width},{height}) "
            f"exceeds tile dimensions ({tile_info.width}x{tile_info.height})"
        )

    # Convert duration to milliseconds
    duration_ms = int(duration * 1000)

    # Send copy command
    await self.connection.request(
        packets.Tile.CopyFrameBuffer(
            tile_index=tile_index,
            length=1,
            src_fb_index=src_fb_index,
            dst_fb_index=dst_fb_index,
            src_x=src_x,
            src_y=src_y,
            dst_x=dst_x,
            dst_y=dst_y,
            width=width,
            height=height,
            duration=duration_ms,
        ),
    )

    _LOGGER.debug(
        {
            "class": "Device",
            "method": "copy_frame_buffer",
            "action": "change",
            "values": {
                "tile_index": tile_index,
                "src_fb_index": src_fb_index,
                "dst_fb_index": dst_fb_index,
                "src_x": src_x,
                "src_y": src_y,
                "dst_x": dst_x,
                "dst_y": dst_y,
                "width": width,
                "height": height,
                "duration": duration_ms,
            },
        }
    )
````

##### set_morph_effect

```python
set_morph_effect(
    palette: list[HSBK], speed: float = 5.0, duration: float = 0.0
) -> None
```

Apply a morph effect that transitions through a color palette.

| PARAMETER  | DESCRIPTION                                                                                  |
| ---------- | -------------------------------------------------------------------------------------------- |
| `palette`  | List of colors to morph between (2-16 colors) **TYPE:** `list[HSBK]`                         |
| `speed`    | Speed in seconds per cycle (default 5.0) **TYPE:** `float` **DEFAULT:** `5.0`                |
| `duration` | Total duration in seconds (0 for infinite, default 0.0) **TYPE:** `float` **DEFAULT:** `0.0` |

| RAISES       | DESCRIPTION           |
| ------------ | --------------------- |
| `ValueError` | If palette is invalid |

Example

```python
# Morph between red, green, and blue
palette = [
    HSBK.from_rgb(255, 0, 0),
    HSBK.from_rgb(0, 255, 0),
    HSBK.from_rgb(0, 0, 255),
]
await tile.set_morph_effect(palette, speed=5.0)
```

Source code in `src/lifx/devices/tile.py`

````python
async def set_morph_effect(
    self,
    palette: list[HSBK],
    speed: float = 5.0,
    duration: float = 0.0,
) -> None:
    """Apply a morph effect that transitions through a color palette.

    Args:
        palette: List of colors to morph between (2-16 colors)
        speed: Speed in seconds per cycle (default 5.0)
        duration: Total duration in seconds (0 for infinite, default 0.0)

    Raises:
        ValueError: If palette is invalid

    Example:
        ```python
        # Morph between red, green, and blue
        palette = [
            HSBK.from_rgb(255, 0, 0),
            HSBK.from_rgb(0, 255, 0),
            HSBK.from_rgb(0, 0, 255),
        ]
        await tile.set_morph_effect(palette, speed=5.0)
        ```
    """
    if len(palette) < 2:
        raise ValueError("Palette must have at least 2 colors")
    if len(palette) > 16:
        raise ValueError(f"Palette too large: {len(palette)} colors (max 16)")

    # Convert speed to milliseconds
    speed_ms = int(speed * 1000)

    # Convert duration to nanoseconds
    duration_ns = int(duration * 1_000_000_000)

    await self.set_tile_effect(
        TileEffect(
            effect_type=TileEffectType.MORPH,
            speed=speed_ms,
            duration=duration_ns,
            palette=palette,
        )
    )

    _LOGGER.debug(
        {
            "class": "Device",
            "method": "set_morph_effect",
            "action": "change",
            "values": {
                "palette_count": len(palette),
                "speed": speed,
                "duration": duration,
            },
        }
    )
````

##### set_flame_effect

```python
set_flame_effect(
    speed: float = 5.0, duration: float = 0.0, palette: list[HSBK] | None = None
) -> None
```

Apply a flame effect.

| PARAMETER  | DESCRIPTION                                                                                  |
| ---------- | -------------------------------------------------------------------------------------------- |
| `speed`    | Effect speed in seconds per cycle (default 5.0) **TYPE:** `float` **DEFAULT:** `5.0`         |
| `duration` | Total duration in seconds (0 for infinite, default 0.0) **TYPE:** `float` **DEFAULT:** `0.0` |
| `palette`  | Optional color palette (default: fire colors) **TYPE:** \`list[HSBK]                         |

Example

```python
# Apply default flame effect
await tile.set_flame_effect()

# Custom flame colors
palette = [
    HSBK.from_rgb(255, 0, 0),  # Red
    HSBK.from_rgb(255, 100, 0),  # Orange
    HSBK.from_rgb(255, 200, 0),  # Yellow
]
await tile.set_flame_effect(speed=3.0, palette=palette)
```

Source code in `src/lifx/devices/tile.py`

````python
async def set_flame_effect(
    self,
    speed: float = 5.0,
    duration: float = 0.0,
    palette: list[HSBK] | None = None,
) -> None:
    """Apply a flame effect.

    Args:
        speed: Effect speed in seconds per cycle (default 5.0)
        duration: Total duration in seconds (0 for infinite, default 0.0)
        palette: Optional color palette (default: fire colors)

    Example:
        ```python
        # Apply default flame effect
        await tile.set_flame_effect()

        # Custom flame colors
        palette = [
            HSBK.from_rgb(255, 0, 0),  # Red
            HSBK.from_rgb(255, 100, 0),  # Orange
            HSBK.from_rgb(255, 200, 0),  # Yellow
        ]
        await tile.set_flame_effect(speed=3.0, palette=palette)
        ```
    """
    if palette is None:
        # Default fire palette
        palette = [
            HSBK(0, 1.0, 1.0, 3500),  # Red
            HSBK(30, 1.0, 1.0, 3500),  # Orange
            HSBK(45, 1.0, 0.8, 3500),  # Yellow-orange
        ]

    # Convert speed to milliseconds
    speed_ms = int(speed * 1000)

    # Convert duration to nanoseconds
    duration_ns = int(duration * 1_000_000_000)

    await self.set_tile_effect(
        TileEffect(
            effect_type=TileEffectType.FLAME,
            speed=speed_ms,
            duration=duration_ns,
            palette=palette,
        )
    )

    _LOGGER.debug(
        {
            "class": "Device",
            "method": "set_flame_effect",
            "action": "change",
            "values": {
                "palette_count": len(palette),
                "speed": speed,
                "duration": duration,
            },
        }
    )
````

##### apply_theme

```python
apply_theme(
    theme: Theme, power_on: bool = False, duration: float = 0.0
) -> None
```

Apply a theme to this tile device.

Distributes theme colors across all tiles in the chain using Canvas-based rendering to create natural color splotches that grow outward.

| PARAMETER  | DESCRIPTION                                                         |
| ---------- | ------------------------------------------------------------------- |
| `theme`    | Theme to apply **TYPE:** `Theme`                                    |
| `power_on` | Turn on the device **TYPE:** `bool` **DEFAULT:** `False`            |
| `duration` | Transition duration in seconds **TYPE:** `float` **DEFAULT:** `0.0` |

Example

```python
from lifx.theme import get_theme

theme = get_theme("sunset")
await tile.apply_theme(theme, power_on=True, duration=2.0)
```

Source code in `src/lifx/devices/tile.py`

````python
async def apply_theme(
    self,
    theme: Theme,
    power_on: bool = False,
    duration: float = 0.0,
) -> None:
    """Apply a theme to this tile device.

    Distributes theme colors across all tiles in the chain using Canvas-based
    rendering to create natural color splotches that grow outward.

    Args:
        theme: Theme to apply
        power_on: Turn on the device
        duration: Transition duration in seconds

    Example:
        ```python
        from lifx.theme import get_theme

        theme = get_theme("sunset")
        await tile.apply_theme(theme, power_on=True, duration=2.0)
        ```
    """
    from lifx.theme.generators import MatrixGenerator

    # Get tile dimensions
    tiles = await self.get_tile_chain()
    if not tiles:
        _LOGGER.warning("No tiles available, skipping theme application")
        return

    # Build coords_and_sizes for all tiles
    left_x = 0
    coords_and_sizes = []
    for tile in tiles:
        coords_and_sizes.append(((left_x, 0), (tile.width, tile.height)))
        left_x += tile.width

    # Create generator with all tile coordinates
    generator = MatrixGenerator(coords_and_sizes)

    # Generate colors for all tiles at once
    tile_colors_list = generator.get_theme_colors(theme)

    # Check if device is on
    is_on = await self.get_power()

    # Determine duration for color setting
    color_duration = 0 if (power_on and not is_on) else duration

    # Apply colors to each tile
    for tile_idx, colors_flat in enumerate(tile_colors_list):
        tile_info = tiles[tile_idx]

        # Convert to 2D grid for set_tile_colors
        colors_2d = []
        for y in range(tile_info.height):
            row = []
            for x in range(tile_info.width):
                idx = y * tile_info.width + x
                if idx < len(colors_flat):
                    row.append(colors_flat[idx])
                else:
                    row.append(HSBK(0, 0, 1.0, 3500))  # White fallback
            colors_2d.append(row)

        # Apply colors to tile
        await self.set_tile_colors(tile_idx, colors_2d, duration=color_duration)

    # Turn on if requested
    if power_on and not is_on:
        await self.set_power(True, duration=duration)
````

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
            if light.has_extended_multizone:
                await light.get_extended_color_zones()
            elif light.has_multizone:
                await light.get_color_zones()
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
