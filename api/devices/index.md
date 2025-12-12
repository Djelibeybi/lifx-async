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

Bases: `Generic[StateT]`

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
| `connect`           | Create and return a fully initialized device instance.  |
| `get_mac_address`   | Calculate and return the MAC address for this device.   |
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
| `close`             | Close device connection and cleanup resources.          |
| `refresh_state`     | Refresh device state from hardware.                     |

| ATTRIBUTE       | DESCRIPTION                                                     |
| --------------- | --------------------------------------------------------------- |
| `capabilities`  | Get device product capabilities. **TYPE:** \`ProductInfo        |
| `state`         | Get device state if available. **TYPE:** \`StateT               |
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

##### state

```python
state: StateT | None
```

Get device state if available.

State is populated by the connect() factory method or by calling \_initialize_state() directly. Returns None if state has not been initialized.

| RETURNS  | DESCRIPTION |
| -------- | ----------- |
| \`StateT | None\`      |

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
````

##### connect

```python
connect(
    ip: str,
    serial: str | None = None,
    port: int = LIFX_UDP_PORT,
    timeout: float = DEFAULT_REQUEST_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> (
    Light
    | HevLight
    | InfraredLight
    | MultiZoneLight
    | MatrixLight
    | CeilingLight
)
```

Create and return a fully initialized device instance.

This factory method creates the appropriate device type (Light, etc) based on the device's capabilities and initializes its state. The returned device MUST be used with an async context manager.

The returned device subclass has guaranteed initialized state - the state property will never be None for devices created via this method.

| PARAMETER     | DESCRIPTION                                                                                                           |
| ------------- | --------------------------------------------------------------------------------------------------------------------- |
| `ip`          | IP address of the device **TYPE:** `str`                                                                              |
| `serial`      | Optional serial number (12-digit hex, with or without colons). If None, queries device to get serial. **TYPE:** \`str |
| `port`        | Port number (default LIFX_UDP_PORT) **TYPE:** `int` **DEFAULT:** `LIFX_UDP_PORT`                                      |
| `timeout`     | Request timeout for this device instance **TYPE:** `float` **DEFAULT:** `DEFAULT_REQUEST_TIMEOUT`                     |
| `max_retries` | Maximum number of retry attempts **TYPE:** `int` **DEFAULT:** `DEFAULT_MAX_RETRIES`                                   |

| RETURNS | DESCRIPTION |
| ------- | ----------- |
| \`Light | HevLight    |
| \`Light | HevLight    |

| RAISES                    | DESCRIPTION                            |
| ------------------------- | -------------------------------------- |
| `LifxDeviceNotFoundError` | If device cannot be found or contacted |
| `LifxTimeoutError`        | If device does not respond             |
| `ValueError`              | If serial format is invalid            |

Example

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

Source code in `src/lifx/devices/base.py`

````python
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
````

##### get_mac_address

```python
get_mac_address() -> str
```

Calculate and return the MAC address for this device.

Source code in `src/lifx/devices/base.py`

```python
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
```

##### get_label

```python
get_label() -> str
```

Get device label/name.

Always fetches from device. Use the `label` property to access stored value.

| RETURNS | DESCRIPTION                                 |
| ------- | ------------------------------------------- |
| `str`   | Device label as string (max 32 bytes UTF-8) |

| RAISES                        | DESCRIPTION                            |
| ----------------------------- | -------------------------------------- |
| `LifxDeviceNotFoundError`     | If device is not connected             |
| `LifxTimeoutError`            | If device does not respond             |
| `LifxProtocolError`           | If response is invalid                 |
| `LifxUnsupportedCommandError` | If device doesn't support this command |

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
````

##### set_label

```python
set_label(label: str) -> None
```

Set device label/name.

| PARAMETER | DESCRIPTION                                           |
| --------- | ----------------------------------------------------- |
| `label`   | New device label (max 32 bytes UTF-8) **TYPE:** `str` |

| RAISES                        | DESCRIPTION                            |
| ----------------------------- | -------------------------------------- |
| `ValueError`                  | If label is too long                   |
| `LifxDeviceNotFoundError`     | If device is not connected             |
| `LifxTimeoutError`            | If device does not respond             |
| `LifxUnsupportedCommandError` | If device doesn't support this command |

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

| RAISES                        | DESCRIPTION                            |
| ----------------------------- | -------------------------------------- |
| `LifxDeviceNotFoundError`     | If device is not connected             |
| `LifxTimeoutError`            | If device does not respond             |
| `LifxProtocolError`           | If response is invalid                 |
| `LifxUnsupportedCommandError` | If device doesn't support this command |

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
````

##### set_power

```python
set_power(level: bool | int) -> None
```

Set device power state.

| PARAMETER | DESCRIPTION                                                 |
| --------- | ----------------------------------------------------------- |
| `level`   | True/65535 to turn on, False/0 to turn off **TYPE:** \`bool |

| RAISES                        | DESCRIPTION                            |
| ----------------------------- | -------------------------------------- |
| `ValueError`                  | If integer value is not 0 or 65535     |
| `LifxDeviceNotFoundError`     | If device is not connected             |
| `LifxTimeoutError`            | If device does not respond             |
| `LifxUnsupportedCommandError` | If device doesn't support this command |

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

| RAISES                        | DESCRIPTION                            |
| ----------------------------- | -------------------------------------- |
| `LifxDeviceNotFoundError`     | If device is not connected             |
| `LifxTimeoutError`            | If device does not respond             |
| `LifxProtocolError`           | If response is invalid                 |
| `LifxUnsupportedCommandError` | If device doesn't support this command |

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

| RAISES                        | DESCRIPTION                            |
| ----------------------------- | -------------------------------------- |
| `LifxDeviceNotFoundError`     | If device is not connected             |
| `LifxTimeoutError`            | If device does not respond             |
| `LifxProtocolError`           | If response is invalid                 |
| `LifxUnsupportedCommandError` | If device doesn't support this command |

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
````

##### get_wifi_info

```python
get_wifi_info() -> WifiInfo
```

Get device WiFi module information.

Always fetches from device.

| RETURNS    | DESCRIPTION                            |
| ---------- | -------------------------------------- |
| `WifiInfo` | WifiInfo with signal strength and RSSI |

| RAISES                        | DESCRIPTION                            |
| ----------------------------- | -------------------------------------- |
| `LifxDeviceNotFoundError`     | If device is not connected             |
| `LifxTimeoutError`            | If device does not respond             |
| `LifxProtocolError`           | If response is invalid                 |
| `LifxUnsupportedCommandError` | If device doesn't support this command |

Example

```python
wifi_info = await device.get_wifi_info()
print(f"WiFi signal: {wifi_info.signal}")
print(f"WiFi RSSI: {wifi_info.rssi}")
```

Source code in `src/lifx/devices/base.py`

````python
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

| RAISES                        | DESCRIPTION                            |
| ----------------------------- | -------------------------------------- |
| `LifxDeviceNotFoundError`     | If device is not connected             |
| `LifxTimeoutError`            | If device does not respond             |
| `LifxProtocolError`           | If response is invalid                 |
| `LifxUnsupportedCommandError` | If device doesn't support this command |

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

| RAISES                        | DESCRIPTION                            |
| ----------------------------- | -------------------------------------- |
| `LifxDeviceNotFoundError`     | If device is not connected             |
| `LifxTimeoutError`            | If device does not respond             |
| `LifxProtocolError`           | If response is invalid                 |
| `LifxUnsupportedCommandError` | If device doesn't support this command |

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
````

##### get_location

```python
get_location() -> CollectionInfo
```

Get device location information.

Always fetches from device.

| RETURNS          | DESCRIPTION                                                     |
| ---------------- | --------------------------------------------------------------- |
| `CollectionInfo` | CollectionInfo with location UUID, label, and updated timestamp |

| RAISES                        | DESCRIPTION                            |
| ----------------------------- | -------------------------------------- |
| `LifxDeviceNotFoundError`     | If device is not connected             |
| `LifxTimeoutError`            | If device does not respond             |
| `LifxProtocolError`           | If response is invalid                 |
| `LifxUnsupportedCommandError` | If device doesn't support this command |

Example

```python
location = await device.get_location()
print(f"Location: {location.label}")
print(f"Location ID: {location.uuid}")
```

Source code in `src/lifx/devices/base.py`

````python
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

| RAISES                        | DESCRIPTION                            |
| ----------------------------- | -------------------------------------- |
| `LifxDeviceNotFoundError`     | If device is not connected             |
| `LifxTimeoutError`            | If device does not respond             |
| `ValueError`                  | If label is invalid                    |
| `LifxUnsupportedCommandError` | If device doesn't support this command |

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
````

##### get_group

```python
get_group() -> CollectionInfo
```

Get device group information.

Always fetches from device.

| RETURNS          | DESCRIPTION                                                  |
| ---------------- | ------------------------------------------------------------ |
| `CollectionInfo` | CollectionInfo with group UUID, label, and updated timestamp |

| RAISES                        | DESCRIPTION                            |
| ----------------------------- | -------------------------------------- |
| `LifxDeviceNotFoundError`     | If device is not connected             |
| `LifxTimeoutError`            | If device does not respond             |
| `LifxProtocolError`           | If response is invalid                 |
| `LifxUnsupportedCommandError` | If device doesn't support this command |

Example

```python
group = await device.get_group()
print(f"Group: {group.label}")
print(f"Group ID: {group.uuid}")
```

Source code in `src/lifx/devices/base.py`

````python
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

| RAISES                        | DESCRIPTION                            |
| ----------------------------- | -------------------------------------- |
| `LifxDeviceNotFoundError`     | If device is not connected             |
| `LifxTimeoutError`            | If device does not respond             |
| `ValueError`                  | If label is invalid                    |
| `LifxUnsupportedCommandError` | If device doesn't support this command |

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
````

##### set_reboot

```python
set_reboot() -> None
```

Reboot the device.

This sends a reboot command to the device. The device will disconnect and restart. You should disconnect from the device after calling this method.

| RAISES                        | DESCRIPTION                            |
| ----------------------------- | -------------------------------------- |
| `LifxDeviceNotFoundError`     | If device is not connected             |
| `LifxTimeoutError`            | If device does not respond             |
| `LifxUnsupportedCommandError` | If device doesn't support this command |

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
````

##### close

```python
close() -> None
```

Close device connection and cleanup resources.

Cancels any pending refresh tasks and closes the network connection. Called automatically when exiting the async context manager.

Source code in `src/lifx/devices/base.py`

```python
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
```

##### refresh_state

```python
refresh_state() -> None
```

Refresh device state from hardware.

Fetches current state from device and updates the state instance. Base implementation fetches label, power, and updates timestamp. Subclasses override to add device-specific state updates.

| RAISES                    | DESCRIPTION                       |
| ------------------------- | --------------------------------- |
| `RuntimeError`            | If state has not been initialized |
| `LifxTimeoutError`        | If device does not respond        |
| `LifxDeviceNotFoundError` | If device cannot be reached       |

Source code in `src/lifx/devices/base.py`

```python
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
```

## Light

The `Light` class provides color control and effects for standard LIFX lights.

### Light

```python
Light(*args, **kwargs)
```

Bases: `Device[LightState]`

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

| METHOD                    | DESCRIPTION                                                             |
| ------------------------- | ----------------------------------------------------------------------- |
| `get_color`               | Get current light color, power, and label.                              |
| `set_color`               | Set light color.                                                        |
| `set_brightness`          | Set light brightness only, preserving hue, saturation, and temperature. |
| `set_kelvin`              | Set light color temperature, preserving brightness. Saturation is       |
| `set_hue`                 | Set light hue only, preserving saturation, brightness, and temperature. |
| `set_saturation`          | Set light saturation only, preserving hue, brightness, and temperature. |
| `get_power`               | Get light power state (specific to light, not device).                  |
| `get_ambient_light_level` | Get ambient light level from device sensor.                             |
| `set_power`               | Set light power state (specific to light, not device).                  |
| `set_waveform`            | Apply a waveform effect to the light.                                   |
| `set_waveform_optional`   | Apply a waveform effect with selective color component control.         |
| `pulse`                   | Pulse the light to a specific color.                                    |
| `breathe`                 | Make the light breathe to a specific color.                             |
| `apply_theme`             | Apply a theme to this light.                                            |
| `refresh_state`           | Refresh light state from hardware.                                      |

| ATTRIBUTE    | DESCRIPTION                                                                                        |
| ------------ | -------------------------------------------------------------------------------------------------- |
| `state`      | Get light state (guaranteed to be initialized when using Device.connect()). **TYPE:** `LightState` |
| `min_kelvin` | Get the minimum supported kelvin value if available. **TYPE:** \`int                               |
| `max_kelvin` | Get the maximum supported kelvin value if available. **TYPE:** \`int                               |

Source code in `src/lifx/devices/light.py`

```python
def __init__(self, *args, **kwargs) -> None:
    """Initialize Light with additional state attributes."""
    super().__init__(*args, **kwargs)
```

#### Attributes

##### state

```python
state: LightState
```

Get light state (guaranteed to be initialized when using Device.connect()).

| RETURNS      | DESCRIPTION                         |
| ------------ | ----------------------------------- |
| `LightState` | LightState with current light state |

| RAISES         | DESCRIPTION                             |
| -------------- | --------------------------------------- |
| `RuntimeError` | If accessed before state initialization |

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

| RAISES                        | DESCRIPTION                            |
| ----------------------------- | -------------------------------------- |
| `LifxDeviceNotFoundError`     | If device is not connected             |
| `LifxTimeoutError`            | If device does not respond             |
| `LifxProtocolError`           | If response is invalid                 |
| `LifxUnsupportedCommandError` | If device doesn't support this command |

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
        LifxUnsupportedCommandError: If device doesn't support this command

    Example:
        ```python
        color, power, label = await light.get_color()
        print(f"{label}: Hue: {color.hue}°, Power: {'ON' if power > 0 else 'OFF'}")
        ```
    """
    # Request automatically unpacks response and decodes labels
    state = await self.connection.request(packets.Light.GetColor())
    self._raise_if_unhandled(state)

    # Convert from protocol HSBK to user-friendly HSBK
    color = HSBK.from_protocol(state.color)
    power = state.power
    label = state.label

    # Store label from StateColor response
    self._label = label  # Already decoded to string

    # Update state if it exists (including all subclasses)
    if self._state is not None:
        # Update base fields available on all device states
        self._state.power = power
        self._state.label = label

        if hasattr(self._state, "color"):
            self._state.color = color

        self._state.last_updated = __import__("time").time()

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

| RAISES                        | DESCRIPTION                            |
| ----------------------------- | -------------------------------------- |
| `LifxDeviceNotFoundError`     | If device is not connected             |
| `LifxTimeoutError`            | If device does not respond             |
| `LifxUnsupportedCommandError` | If device doesn't support this command |

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
        LifxUnsupportedCommandError: If device doesn't support this command

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
    result = await self.connection.request(
        packets.Light.SetColor(
            color=protocol_color,
            duration=duration_ms,
        ),
    )
    self._raise_if_unhandled(result)

    _LOGGER.debug(
        {
            "class": "Light",
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

    # Update state on acknowledgement
    if result and self._state is not None:
        self._state.color = color
        await self._schedule_refresh()
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
    if not (MIN_BRIGHTNESS <= brightness <= MAX_BRIGHTNESS):
        raise ValueError(
            f"Brightness must be between {MIN_BRIGHTNESS} "
            f"and {MAX_BRIGHTNESS}, got {brightness}"
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
    if not (MIN_KELVIN <= kelvin <= MAX_KELVIN):
        raise ValueError(
            f"Kelvin must be between {MIN_KELVIN} and {MAX_KELVIN}, got {kelvin}"
        )

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
set_hue(hue: int, duration: float = 0.0) -> None
```

Set light hue only, preserving saturation, brightness, and temperature.

| PARAMETER  | DESCRIPTION                                                                       |
| ---------- | --------------------------------------------------------------------------------- |
| `hue`      | Hue in degrees (0-360) **TYPE:** `int`                                            |
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
async def set_hue(self, hue: int, duration: float = 0.0) -> None:
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
    if not (MIN_HUE <= hue <= MAX_HUE):
        raise ValueError(f"Hue must be between {MIN_HUE} and {MAX_HUE}, got {hue}")

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
    if not (MIN_SATURATION <= saturation <= MAX_SATURATION):
        raise ValueError(
            f"Saturation must be between {MIN_SATURATION} "
            f"and {MAX_SATURATION}, got {saturation}"
        )

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

| RAISES                        | DESCRIPTION                            |
| ----------------------------- | -------------------------------------- |
| `LifxDeviceNotFoundError`     | If device is not connected             |
| `LifxTimeoutError`            | If device does not respond             |
| `LifxProtocolError`           | If response is invalid                 |
| `LifxUnsupportedCommandError` | If device doesn't support this command |

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
        LifxUnsupportedCommandError: If device doesn't support this command

    Example:
        ```python
        level = await light.get_power()
        print(f"Light power: {'ON' if level > 0 else 'OFF'}")
        ```
    """
    # Request automatically unpacks response
    state = await self.connection.request(packets.Light.GetPower())
    self._raise_if_unhandled(state)

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

##### get_ambient_light_level

```python
get_ambient_light_level() -> float
```

Get ambient light level from device sensor.

Always fetches from device (volatile property, not cached).

This method queries the device's ambient light sensor to get the current lux reading. Devices without ambient light sensors will return 0.0.

| RETURNS | DESCRIPTION                                              |
| ------- | -------------------------------------------------------- |
| `float` | Ambient light level in lux (0.0 if device has no sensor) |

| RAISES                        | DESCRIPTION                            |
| ----------------------------- | -------------------------------------- |
| `LifxDeviceNotFoundError`     | If device is not connected             |
| `LifxTimeoutError`            | If device does not respond             |
| `LifxProtocolError`           | If response is invalid                 |
| `LifxUnsupportedCommandError` | If device doesn't support this command |

Example

```python
lux = await light.get_ambient_light_level()
if lux > 0:
    print(f"Ambient light: {lux} lux")
else:
    print("No ambient light sensor or completely dark")
```

Source code in `src/lifx/devices/light.py`

````python
async def get_ambient_light_level(self) -> float:
    """Get ambient light level from device sensor.

    Always fetches from device (volatile property, not cached).

    This method queries the device's ambient light sensor to get the current
    lux reading. Devices without ambient light sensors will return 0.0.

    Returns:
        Ambient light level in lux (0.0 if device has no sensor)

    Raises:
        LifxDeviceNotFoundError: If device is not connected
        LifxTimeoutError: If device does not respond
        LifxProtocolError: If response is invalid
        LifxUnsupportedCommandError: If device doesn't support this command

    Example:
        ```python
        lux = await light.get_ambient_light_level()
        if lux > 0:
            print(f"Ambient light: {lux} lux")
        else:
            print("No ambient light sensor or completely dark")
        ```
    """
    # Request automatically unpacks response
    state = await self.connection.request(packets.Sensor.GetAmbientLight())
    self._raise_if_unhandled(state)

    _LOGGER.debug(
        {
            "class": "Light",
            "method": "get_ambient_light_level",
            "action": "query",
            "reply": {"lux": state.lux},
        }
    )

    return state.lux
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

| RAISES                        | DESCRIPTION                            |
| ----------------------------- | -------------------------------------- |
| `ValueError`                  | If integer value is not 0 or 65535     |
| `LifxDeviceNotFoundError`     | If device is not connected             |
| `LifxTimeoutError`            | If device does not respond             |
| `LifxUnsupportedCommandError` | If device doesn't support this command |

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
        LifxUnsupportedCommandError: If device doesn't support this command

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
    result = await self.connection.request(
        packets.Light.SetPower(level=power_level, duration=duration_ms),
    )
    self._raise_if_unhandled(result)

    _LOGGER.debug(
        {
            "class": "Light",
            "method": "set_power",
            "action": "change",
            "values": {"level": power_level, "duration": duration_ms},
        }
    )

    # Update state on acknowledgement
    if result and self._state is not None:
        self._state.power = power_level

    # Schedule refresh to validate state
    if self._state is not None:
        await self._schedule_refresh()
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

| RAISES                        | DESCRIPTION                            |
| ----------------------------- | -------------------------------------- |
| `ValueError`                  | If parameters are out of range         |
| `LifxDeviceNotFoundError`     | If device is not connected             |
| `LifxTimeoutError`            | If device does not respond             |
| `LifxUnsupportedCommandError` | If device doesn't support this command |

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
        LifxUnsupportedCommandError: If device doesn't support this command

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
    result = await self.connection.request(
        packets.Light.SetWaveform(
            transient=bool(transient),
            color=protocol_color,
            period=period_ms,
            cycles=cycles,
            skew_ratio=skew_ratio_i16,
            waveform=waveform,
        ),
    )
    self._raise_if_unhandled(result)
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

    # Schedule refresh to update state
    if self._state is not None:
        await self._schedule_refresh()
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

| RAISES                        | DESCRIPTION                            |
| ----------------------------- | -------------------------------------- |
| `ValueError`                  | If parameters are out of range         |
| `LifxDeviceNotFoundError`     | If device is not connected             |
| `LifxTimeoutError`            | If device does not respond             |
| `LifxUnsupportedCommandError` | If device doesn't support this command |

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
        LifxUnsupportedCommandError: If device doesn't support this command

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
    result = await self.connection.request(
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
    self._raise_if_unhandled(result)
    _LOGGER.debug(
        {
            "class": "Light",
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

    # Update state on acknowledgement (only if non-transient)
    if result and not transient and self._state is not None:
        # Create a new color with only the specified components updated
        current = self._state.color
        new_color = HSBK(
            hue=color.hue if set_hue else current.hue,
            saturation=color.saturation if set_saturation else current.saturation,
            brightness=color.brightness if set_brightness else current.brightness,
            kelvin=color.kelvin if set_kelvin else current.kelvin,
        )
        self._state.color = new_color

    # Schedule refresh to validate state
    if self._state is not None:
        await self._schedule_refresh()
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

##### refresh_state

```python
refresh_state() -> None
```

Refresh light state from hardware.

Fetches color (which includes power and label) and updates state.

| RAISES                    | DESCRIPTION                       |
| ------------------------- | --------------------------------- |
| `RuntimeError`            | If state has not been initialized |
| `LifxTimeoutError`        | If device does not respond        |
| `LifxDeviceNotFoundError` | If device cannot be reached       |

Source code in `src/lifx/devices/light.py`

```python
async def refresh_state(self) -> None:
    """Refresh light state from hardware.

    Fetches color (which includes power and label) and updates state.

    Raises:
        RuntimeError: If state has not been initialized
        LifxTimeoutError: If device does not respond
        LifxDeviceNotFoundError: If device cannot be reached
    """
    import time

    if self._state is None:
        await self._initialize_state()
        return

    # GetColor returns color, power, and label in one request
    color, power, label = await self.get_color()

    self._state.color = color
    self._state.power = power
    self._state.label = label
    self._state.last_updated = time.time()
```

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
| `refresh_state`       | Refresh HEV light state from hardware.     |

| ATTRIBUTE    | DESCRIPTION                                                                             |
| ------------ | --------------------------------------------------------------------------------------- |
| `state`      | Get HEV light state (guaranteed when using Device.connect()). **TYPE:** `HevLightState` |
| `hev_config` | Get cached HEV configuration if available. **TYPE:** \`HevConfig                        |
| `hev_result` | Get cached last HEV cycle result if available. **TYPE:** \`LightLastHevCycleResult      |

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

##### state

```python
state: HevLightState
```

Get HEV light state (guaranteed when using Device.connect()).

| RETURNS         | DESCRIPTION                                |
| --------------- | ------------------------------------------ |
| `HevLightState` | HevLightState with current HEV light state |

| RAISES         | DESCRIPTION                             |
| -------------- | --------------------------------------- |
| `RuntimeError` | If accessed before state initialization |

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

| RAISES                        | DESCRIPTION                            |
| ----------------------------- | -------------------------------------- |
| `LifxDeviceNotFoundError`     | If device is not connected             |
| `LifxTimeoutError`            | If device does not respond             |
| `LifxProtocolError`           | If response is invalid                 |
| `LifxUnsupportedCommandError` | If device doesn't support this command |

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
        LifxUnsupportedCommandError: If device doesn't support this command

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
    self._raise_if_unhandled(state)

    # Create state object
    cycle_state = HevCycleState(
        duration_s=state.duration_s,
        remaining_s=state.remaining_s,
        last_power=state.last_power,
    )

    # Update state if it exists
    if self._state is not None and hasattr(self._state, "hev_cycle"):
        self._state.hev_cycle = cycle_state
        self._state.last_updated = __import__("time").time()

    # Update state if it exists
    if self._state is not None and hasattr(self._state, "hev_cycle"):
        self._state.hev_cycle = cycle_state
        self._state.last_updated = __import__("time").time()

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

| RAISES                        | DESCRIPTION                            |
| ----------------------------- | -------------------------------------- |
| `ValueError`                  | If duration is negative                |
| `LifxDeviceNotFoundError`     | If device is not connected             |
| `LifxTimeoutError`            | If device does not respond             |
| `LifxUnsupportedCommandError` | If device doesn't support this command |

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
        LifxUnsupportedCommandError: If device doesn't support this command

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
    result = await self.connection.request(
        packets.Light.SetHevCycle(
            enable=enable,
            duration_s=duration_seconds,
        ),
    )
    self._raise_if_unhandled(result)

    _LOGGER.debug(
        {
            "class": "HevLight",
            "method": "set_hev_cycle",
            "action": "change",
            "values": {"enable": enable, "duration_s": duration_seconds},
        }
    )

    # Schedule debounced refresh to update HEV cycle state
    # (No optimistic update - cycle state is complex)
    if self._state is not None:
        await self._schedule_refresh()
````

##### get_hev_config

```python
get_hev_config() -> HevConfig
```

Get HEV cycle configuration.

| RETURNS     | DESCRIPTION                                             |
| ----------- | ------------------------------------------------------- |
| `HevConfig` | HevConfig with indication and default duration settings |

| RAISES                        | DESCRIPTION                            |
| ----------------------------- | -------------------------------------- |
| `LifxDeviceNotFoundError`     | If device is not connected             |
| `LifxTimeoutError`            | If device does not respond             |
| `LifxProtocolError`           | If response is invalid                 |
| `LifxUnsupportedCommandError` | If device doesn't support this command |

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
        LifxUnsupportedCommandError: If device doesn't support this command

    Example:
        ```python
        config = await light.get_hev_config()
        print(f"Default duration: {config.duration_s}s")
        print(f"Visual indication: {config.indication}")
        ```
    """
    # Request HEV configuration
    state = await self.connection.request(packets.Light.GetHevCycleConfiguration())
    self._raise_if_unhandled(state)

    # Create config object
    config = HevConfig(
        indication=state.indication,
        duration_s=state.duration_s,
    )

    # Store cached state
    self._hev_config = config

    # Update state if it exists
    if self._state is not None and hasattr(self._state, "hev_config"):
        self._state.hev_config = config
        self._state.last_updated = __import__("time").time()

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

| RAISES                        | DESCRIPTION                            |
| ----------------------------- | -------------------------------------- |
| `ValueError`                  | If duration is negative                |
| `LifxDeviceNotFoundError`     | If device is not connected             |
| `LifxTimeoutError`            | If device does not respond             |
| `LifxUnsupportedCommandError` | If device doesn't support this command |

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
        LifxUnsupportedCommandError: If device doesn't support this command

    Example:
        ```python
        # Configure 2-hour default with visual indication
        await light.set_hev_config(indication=True, duration_seconds=7200)
        ```
    """
    if duration_seconds < 0:
        raise ValueError(f"Duration must be non-negative, got {duration_seconds}")

    # Request automatically handles acknowledgement
    result = await self.connection.request(
        packets.Light.SetHevCycleConfiguration(
            indication=indication,
            duration_s=duration_seconds,
        ),
    )
    self._raise_if_unhandled(result)

    _LOGGER.debug(
        {
            "class": "HevLight",
            "method": "set_hev_config",
            "action": "change",
            "values": {"indication": indication, "duration_s": duration_seconds},
        }
    )

    # Update cache and state on acknowledgement
    if result:
        hev_config = HevConfig(indication=indication, duration_s=duration_seconds)
        self._hev_config = hev_config
        if self._state is not None:
            self._state.hev_config = hev_config

    # Schedule refresh to validate state
    if self._state is not None:
        await self._schedule_refresh()
````

##### get_last_hev_result

```python
get_last_hev_result() -> LightLastHevCycleResult
```

Get result of the last HEV cleaning cycle.

| RETURNS                   | DESCRIPTION                                                                  |
| ------------------------- | ---------------------------------------------------------------------------- |
| `LightLastHevCycleResult` | LightLastHevCycleResult enum value indicating success or interruption reason |

| RAISES                        | DESCRIPTION                            |
| ----------------------------- | -------------------------------------- |
| `LifxDeviceNotFoundError`     | If device is not connected             |
| `LifxTimeoutError`            | If device does not respond             |
| `LifxProtocolError`           | If response is invalid                 |
| `LifxUnsupportedCommandError` | If device doesn't support this command |

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
        LifxUnsupportedCommandError: If device doesn't support this command

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
    self._raise_if_unhandled(state)

    # Store cached state
    result = state.result
    self._hev_result = result

    # Update state if it exists
    if self._state is not None and hasattr(self._state, "hev_result"):
        self._state.hev_result = result
        self._state.last_updated = __import__("time").time()

    _LOGGER.debug(
        {
            "class": "Device",
            "method": "get_last_hev_result",
            "action": "query",
            "reply": {"result": result.value},
        }
    )

    return result
````

##### refresh_state

```python
refresh_state() -> None
```

Refresh HEV light state from hardware.

Fetches color, HEV cycle, config, and last result.

| RAISES                    | DESCRIPTION                       |
| ------------------------- | --------------------------------- |
| `RuntimeError`            | If state has not been initialized |
| `LifxTimeoutError`        | If device does not respond        |
| `LifxDeviceNotFoundError` | If device cannot be reached       |

Source code in `src/lifx/devices/hev.py`

```python
async def refresh_state(self) -> None:
    """Refresh HEV light state from hardware.

    Fetches color, HEV cycle, config, and last result.

    Raises:
        RuntimeError: If state has not been initialized
        LifxTimeoutError: If device does not respond
        LifxDeviceNotFoundError: If device cannot be reached
    """
    await super().refresh_state()

    # Fetch all HEV light state
    async with asyncio.TaskGroup() as tg:
        hev_cycle_task = tg.create_task(self.get_hev_cycle())
        hev_result_task = tg.create_task(self.get_last_hev_result())

    hev_cycle = hev_cycle_task.result()
    hev_result = hev_result_task.result()

    self._state.hev_cycle = hev_cycle
    self._state.hev_result = hev_result
```

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

| METHOD          | DESCRIPTION                                 |
| --------------- | ------------------------------------------- |
| `get_infrared`  | Get current infrared brightness.            |
| `set_infrared`  | Set infrared brightness.                    |
| `refresh_state` | Refresh infrared light state from hardware. |

| ATTRIBUTE  | DESCRIPTION                                                                                       |
| ---------- | ------------------------------------------------------------------------------------------------- |
| `state`    | Get infrared light state (guaranteed when using Device.connect()). **TYPE:** `InfraredLightState` |
| `infrared` | Get cached infrared brightness if available. **TYPE:** \`float                                    |

Source code in `src/lifx/devices/infrared.py`

```python
def __init__(self, *args, **kwargs) -> None:
    """Initialize InfraredLight with additional state attributes."""
    super().__init__(*args, **kwargs)
    # Infrared-specific state storage
    self._infrared: float | None = None
```

#### Attributes

##### state

```python
state: InfraredLightState
```

Get infrared light state (guaranteed when using Device.connect()).

| RETURNS              | DESCRIPTION                                          |
| -------------------- | ---------------------------------------------------- |
| `InfraredLightState` | InfraredLightState with current infrared light state |

| RAISES         | DESCRIPTION                             |
| -------------- | --------------------------------------- |
| `RuntimeError` | If accessed before state initialization |

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

| RAISES                        | DESCRIPTION                            |
| ----------------------------- | -------------------------------------- |
| `LifxDeviceNotFoundError`     | If device is not connected             |
| `LifxTimeoutError`            | If device does not respond             |
| `LifxProtocolError`           | If response is invalid                 |
| `LifxUnsupportedCommandError` | If device doesn't support this command |

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
````

##### set_infrared

```python
set_infrared(brightness: float) -> None
```

Set infrared brightness.

| PARAMETER    | DESCRIPTION                                     |
| ------------ | ----------------------------------------------- |
| `brightness` | Infrared brightness (0.0-1.0) **TYPE:** `float` |

| RAISES                        | DESCRIPTION                            |
| ----------------------------- | -------------------------------------- |
| `ValueError`                  | If brightness is out of range          |
| `LifxDeviceNotFoundError`     | If device is not connected             |
| `LifxTimeoutError`            | If device does not respond             |
| `LifxUnsupportedCommandError` | If device doesn't support this command |

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
````

##### refresh_state

```python
refresh_state() -> None
```

Refresh infrared light state from hardware.

Fetches color and infrared brightness.

| RAISES                    | DESCRIPTION                       |
| ------------------------- | --------------------------------- |
| `RuntimeError`            | If state has not been initialized |
| `LifxTimeoutError`        | If device does not respond        |
| `LifxDeviceNotFoundError` | If device cannot be reached       |

Source code in `src/lifx/devices/infrared.py`

```python
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
```

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
| `get_effect`               | Get current multizone effect.                                        |
| `set_effect`               | Set multizone effect.                                                |
| `stop_effect`              | Stop any running multizone effect.                                   |
| `apply_theme`              | Apply a theme across zones.                                          |
| `refresh_state`            | Refresh multizone light state from hardware.                         |

| ATTRIBUTE          | DESCRIPTION                                                                                         |
| ------------------ | --------------------------------------------------------------------------------------------------- |
| `state`            | Get multizone light state (guaranteed when using Device.connect()). **TYPE:** `MultiZoneLightState` |
| `zone_count`       | Get cached zone count if available. **TYPE:** \`int                                                 |
| `multizone_effect` | Get cached multizone effect if available. **TYPE:** \`MultiZoneEffect                               |

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

##### state

```python
state: MultiZoneLightState
```

Get multizone light state (guaranteed when using Device.connect()).

| RETURNS               | DESCRIPTION                                            |
| --------------------- | ------------------------------------------------------ |
| `MultiZoneLightState` | MultiZoneLightState with current multizone light state |

| RAISES         | DESCRIPTION                             |
| -------------- | --------------------------------------- |
| `RuntimeError` | If accessed before state initialization |

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

| RAISES                        | DESCRIPTION                            |
| ----------------------------- | -------------------------------------- |
| `LifxDeviceNotFoundError`     | If device is not connected             |
| `LifxTimeoutError`            | If device does not respond             |
| `LifxProtocolError`           | If response is invalid                 |
| `LifxUnsupportedCommandError` | If device doesn't support this command |

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
        LifxUnsupportedCommandError: If device doesn't support this command

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
    self._raise_if_unhandled(state)

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

| RAISES                        | DESCRIPTION                            |
| ----------------------------- | -------------------------------------- |
| `ValueError`                  | If zone indices are invalid            |
| `LifxDeviceNotFoundError`     | If device is not connected             |
| `LifxTimeoutError`            | If device does not respond             |
| `LifxProtocolError`           | If response is invalid                 |
| `LifxUnsupportedCommandError` | If device doesn't support this command |

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
            self._raise_if_unhandled(state)
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

    # Update state if it exists and we fetched all zones
    if self._state is not None and hasattr(self._state, "zones"):
        if start == 0 and len(result) == zone_count:
            self._state.zones = result
            self._state.last_updated = __import__("time").time()

    # Update state if it exists and we fetched all zones
    if self._state is not None and hasattr(self._state, "zones"):
        if start == 0 and len(result) == zone_count:
            self._state.zones = result
            self._state.last_updated = __import__("time").time()

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

| RAISES                        | DESCRIPTION                            |
| ----------------------------- | -------------------------------------- |
| `ValueError`                  | If zone indices are invalid            |
| `LifxDeviceNotFoundError`     | If device is not connected             |
| `LifxTimeoutError`            | If device does not respond             |
| `LifxProtocolError`           | If response is invalid                 |
| `LifxUnsupportedCommandError` | If device doesn't support this command |

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

    zone_count = await self.get_zone_count()
    end = min(zone_count - 1, end)

    colors: list[HSBK] = []

    # Stream all responses until timeout
    async for packet in self.connection.request_stream(
        packets.MultiZone.GetExtendedColorZones(),
        timeout=2.0,  # Allow time for multiple responses
    ):
        self._raise_if_unhandled(packet)
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

    # Update state if it exists and we fetched all zones
    if self._state is not None and hasattr(self._state, "zones"):
        if start == 0 and len(result) == zone_count:
            self._state.zones = result
            self._state.last_updated = __import__("time").time()

    # Update state if it exists and we fetched all zones
    if self._state is not None and hasattr(self._state, "zones"):
        if start == 0 and len(result) == zone_count:
            self._state.zones = result
            self._state.last_updated = __import__("time").time()

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

| RAISES                        | DESCRIPTION                            |
| ----------------------------- | -------------------------------------- |
| `ValueError`                  | If zone indices are invalid            |
| `LifxDeviceNotFoundError`     | If device is not connected             |
| `LifxTimeoutError`            | If device does not respond             |
| `LifxUnsupportedCommandError` | If device doesn't support this command |

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
        LifxUnsupportedCommandError: If device doesn't support this command

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
````

##### set_extended_color_zones

```python
set_extended_color_zones(
    zone_index: int,
    colors: list[HSBK],
    duration: float = 0.0,
    apply: MultiZoneApplicationRequest = APPLY,
) -> None
```

Set colors for multiple zones efficiently (up to 82 zones per call).

This is more efficient than set_color_zones when setting different colors for many zones at once.

| PARAMETER    | DESCRIPTION                                                                                   |
| ------------ | --------------------------------------------------------------------------------------------- |
| `zone_index` | Starting zone index **TYPE:** `int`                                                           |
| `colors`     | List of HSBK colors to set (max 82) **TYPE:** `list[HSBK]`                                    |
| `duration`   | Transition duration in seconds (default 0.0) **TYPE:** `float` **DEFAULT:** `0.0`             |
| `apply`      | Application mode (default APPLY) **TYPE:** `MultiZoneApplicationRequest` **DEFAULT:** `APPLY` |

| RAISES                        | DESCRIPTION                                         |
| ----------------------------- | --------------------------------------------------- |
| `ValueError`                  | If colors list is too long or zone index is invalid |
| `LifxDeviceNotFoundError`     | If device is not connected                          |
| `LifxTimeoutError`            | If device does not respond                          |
| `LifxUnsupportedCommandError` | If device doesn't support this command              |

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
        LifxUnsupportedCommandError: If device doesn't support this command

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
    result = await self.connection.request(
        packets.MultiZone.SetExtendedColorZones(
            duration=duration_ms,
            apply=apply,
            index=zone_index,
            colors_count=len(colors),
            colors=protocol_colors,
        ),
    )
    self._raise_if_unhandled(result)

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

##### get_effect

```python
get_effect() -> MultiZoneEffect
```

Get current multizone effect.

Always fetches from device. Use the `multizone_effect` property to access stored value.

| RETURNS           | DESCRIPTION                                                           |
| ----------------- | --------------------------------------------------------------------- |
| `MultiZoneEffect` | MultiZoneEffect with either FirmwareEffect.OFF or FirmwareEffect.MOVE |

| RAISES                        | DESCRIPTION                            |
| ----------------------------- | -------------------------------------- |
| `LifxDeviceNotFoundError`     | If device is not connected             |
| `LifxTimeoutError`            | If device does not respond             |
| `LifxProtocolError`           | If response is invalid                 |
| `LifxUnsupportedCommandError` | If device doesn't support this command |

Example

```python
from lifx.protocol.protocol_types import Direction, FirmwareEffect

effect = await light.get_effect()
if effect:
    print(f"Effect: {effect.effect_type.name}, Speed: {effect.speed}ms")
    if effect.effect_type == FirmwareEffect.MOVE:
        print(f"Direction: {effect.direction.name}")
```

Source code in `src/lifx/devices/multizone.py`

````python
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
        self._state.last_updated = __import__("time").time()

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
````

##### set_effect

```python
set_effect(effect: MultiZoneEffect) -> None
```

Set multizone effect.

| PARAMETER | DESCRIPTION                                                |
| --------- | ---------------------------------------------------------- |
| `effect`  | MultiZone effect configuration **TYPE:** `MultiZoneEffect` |

| RAISES                        | DESCRIPTION                            |
| ----------------------------- | -------------------------------------- |
| `LifxDeviceNotFoundError`     | If device is not connected             |
| `LifxTimeoutError`            | If device does not respond             |
| `LifxUnsupportedCommandError` | If device doesn't support this command |

Example

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

Source code in `src/lifx/devices/multizone.py`

````python
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

##### refresh_state

```python
refresh_state() -> None
```

Refresh multizone light state from hardware.

Fetches color, zones, and effect.

| RAISES                    | DESCRIPTION                       |
| ------------------------- | --------------------------------- |
| `RuntimeError`            | If state has not been initialized |
| `LifxTimeoutError`        | If device does not respond        |
| `LifxDeviceNotFoundError` | If device cannot be reached       |

Source code in `src/lifx/devices/multizone.py`

```python
async def refresh_state(self) -> None:
    """Refresh multizone light state from hardware.

    Fetches color, zones, and effect.

    Raises:
        RuntimeError: If state has not been initialized
        LifxTimeoutError: If device does not respond
        LifxDeviceNotFoundError: If device cannot be reached
    """
    await super().refresh_state()

    async with asyncio.TaskGroup() as tg:
        zones_task = tg.create_task(self.get_all_color_zones())
        effect_task = tg.create_task(self.get_effect())

    zones = zones_task.result()
    effect = effect_task.result()

    self._state.zones = zones
    self._state.effect = effect.effect_type
```

## Matrix Light

The `MatrixLight` class controls LIFX matrix devices (tiles, candle, path) with 2D zone control.

### MatrixLight

```python
MatrixLight(*args, **kwargs)
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

See :class:`Light` for parameter documentation.

| METHOD                | DESCRIPTION                                                               |
| --------------------- | ------------------------------------------------------------------------- |
| `get_device_chain`    | Get device chain details (list of Tile objects).                          |
| `set_user_position`   | Position tiles in the chain (only for devices with has_chain capability). |
| `get64`               | Get up to 64 zones of color state from a tile.                            |
| `get_all_tile_colors` | Get colors for all tiles in the chain.                                    |
| `set64`               | Set up to 64 zones of color on a tile.                                    |
| `copy_frame_buffer`   | Copy frame buffer (for tiles with >64 zones).                             |
| `set_matrix_colors`   | Convenience method to set all colors on a tile.                           |
| `get_effect`          | Get current running matrix effect.                                        |
| `set_effect`          | Set matrix effect with configuration.                                     |
| `apply_theme`         | Apply a theme across matrix tiles using Canvas interpolation.             |
| `refresh_state`       | Refresh matrix light state from hardware.                                 |

| ATTRIBUTE      | DESCRIPTION                                                                                   |
| -------------- | --------------------------------------------------------------------------------------------- |
| `state`        | Get matrix light state (guaranteed when using Device.connect()). **TYPE:** `MatrixLightState` |
| `device_chain` | Get cached device chain. **TYPE:** \`list[TileInfo]                                           |
| `tile_count`   | Get number of tiles in the chain. **TYPE:** \`int                                             |
| `tile_effect`  | Get cached tile effect. **TYPE:** \`MatrixEffect                                              |

Source code in `src/lifx/devices/matrix.py`

```python
def __init__(self, *args, **kwargs) -> None:
    """Initialize MatrixLight device.

    See :class:`Light` for parameter documentation.
    """
    super().__init__(*args, **kwargs)
    # Matrix specific properties
    self._device_chain: list[TileInfo] | None = None
    self._tile_effect: MatrixEffect | None = None
```

#### Attributes

##### state

```python
state: MatrixLightState
```

Get matrix light state (guaranteed when using Device.connect()).

| RETURNS            | DESCRIPTION                                      |
| ------------------ | ------------------------------------------------ |
| `MatrixLightState` | MatrixLightState with current matrix light state |

| RAISES         | DESCRIPTION                             |
| -------------- | --------------------------------------- |
| `RuntimeError` | If accessed before state initialization |

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

| RAISES                        | DESCRIPTION                            |
| ----------------------------- | -------------------------------------- |
| `LifxDeviceNotFoundError`     | If device is not connected             |
| `LifxTimeoutError`            | If device does not respond             |
| `LifxUnsupportedCommandError` | If device doesn't support this command |

Example

> > > chain = await matrix.get_device_chain() for tile in chain: ... print(f"Tile {tile.tile_index}: {tile.width}x{tile.height}")

Source code in `src/lifx/devices/matrix.py`

```python
async def get_device_chain(self) -> list[TileInfo]:
    """Get device chain details (list of Tile objects).

    This method fetches the device chain information and caches it.

    Returns:
        List of TileInfo objects describing each tile in the chain

    Raises:
        LifxDeviceNotFoundError: If device is not connected
        LifxTimeoutError: If device does not respond
        LifxUnsupportedCommandError: If device doesn't support this command

    Example:
        >>> chain = await matrix.get_device_chain()
        >>> for tile in chain:
        ...     print(f"Tile {tile.tile_index}: {tile.width}x{tile.height}")
    """
    _LOGGER.debug("Getting device chain for %s", self.label or self.serial)

    response: packets.Tile.StateDeviceChain = await self.connection.request(
        packets.Tile.GetDeviceChain()
    )
    self._raise_if_unhandled(response)

    # Parse tiles from response
    tiles = []
    for i, protocol_tile in enumerate(response.tile_devices):
        # Stop at first zero-width tile (indicates end of chain)
        if protocol_tile.width == 0:
            break
        tiles.append(TileInfo.from_protocol(i, protocol_tile))

    self._device_chain = tiles

    # Update state if it exists
    if self._state is not None and hasattr(self._state, "chain"):
        self._state.chain = tiles
        self._state.tile_count = len(tiles)
        self._state.last_updated = __import__("time").time()

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
    tile_index: int = 0,
    length: int = 1,
    x: int = 0,
    y: int = 0,
    width: int | None = None,
) -> list[HSBK]
```

Get up to 64 zones of color state from a tile.

For devices with ≤64 zones, returns all zones. For devices with >64 zones, returns up to 64 zones due to protocol limitations.

| PARAMETER    | DESCRIPTION                                                                              |
| ------------ | ---------------------------------------------------------------------------------------- |
| `tile_index` | Index of the tile (0-based). Defaults to 0. **TYPE:** `int` **DEFAULT:** `0`             |
| `length`     | Number of tiles to query (usually 1). Defaults to 1. **TYPE:** `int` **DEFAULT:** `1`    |
| `x`          | X coordinate of the rectangle (0-based). Defaults to 0. **TYPE:** `int` **DEFAULT:** `0` |
| `y`          | Y coordinate of the rectangle (0-based). Defaults to 0. **TYPE:** `int` **DEFAULT:** `0` |
| `width`      | Width of the rectangle in zones. Defaults to tile width. **TYPE:** \`int                 |

| RETURNS      | DESCRIPTION                                                               |
| ------------ | ------------------------------------------------------------------------- |
| `list[HSBK]` | List of HSBK colors for the requested zones. For tiles with ≤64 zones,    |
| `list[HSBK]` | returns the actual zone count (e.g., 64 for 8x8, 16 for 4x4). For tiles   |
| `list[HSBK]` | with >64 zones (e.g., 128 for 16x8 Ceiling), returns 64 (protocol limit). |

| RAISES                        | DESCRIPTION                            |
| ----------------------------- | -------------------------------------- |
| `LifxDeviceNotFoundError`     | If device is not connected             |
| `LifxTimeoutError`            | If device does not respond             |
| `LifxUnsupportedCommandError` | If device doesn't support this command |

Example

> > > ###### Get all colors from first tile (no parameters needed)
> > >
> > > colors = await matrix.get64()
> > >
> > > ###### Get colors from specific region
> > >
> > > colors = await matrix.get64(y=4) # Start at row 4

Source code in `src/lifx/devices/matrix.py`

```python
async def get64(
    self,
    tile_index: int = 0,
    length: int = 1,
    x: int = 0,
    y: int = 0,
    width: int | None = None,
) -> list[HSBK]:
    """Get up to 64 zones of color state from a tile.

    For devices with ≤64 zones, returns all zones. For devices with >64 zones,
    returns up to 64 zones due to protocol limitations.

    Args:
        tile_index: Index of the tile (0-based). Defaults to 0.
        length: Number of tiles to query (usually 1). Defaults to 1.
        x: X coordinate of the rectangle (0-based). Defaults to 0.
        y: Y coordinate of the rectangle (0-based). Defaults to 0.
        width: Width of the rectangle in zones. Defaults to tile width.

    Returns:
        List of HSBK colors for the requested zones. For tiles with ≤64 zones,
        returns the actual zone count (e.g., 64 for 8x8, 16 for 4x4). For tiles
        with >64 zones (e.g., 128 for 16x8 Ceiling), returns 64 (protocol limit).

    Raises:
        LifxDeviceNotFoundError: If device is not connected
        LifxTimeoutError: If device does not respond
        LifxUnsupportedCommandError: If device doesn't support this command

    Example:
        >>> # Get all colors from first tile (no parameters needed)
        >>> colors = await matrix.get64()
        >>>
        >>> # Get colors from specific region
        >>> colors = await matrix.get64(y=4)  # Start at row 4
    """
    # Validate parameters
    if x < 0:
        raise ValueError(f"x coordinate must be non-negative, got {x}")
    if y < 0:
        raise ValueError(f"y coordinate must be non-negative, got {y}")
    if width is not None and width <= 0:
        raise ValueError(f"width must be positive, got {width}")

    if self._device_chain is None:
        device_chain = await self.get_device_chain()
    else:
        device_chain = self._device_chain

    if width is None:
        width = device_chain[0].width

    _LOGGER.debug(
        "Getting 64 zones from tile %d (x=%d, y=%d, width=%d) for %s",
        tile_index,
        x,
        y,
        width,
        self.label or self.serial,
    )

    response: packets.Tile.State64 = await self.connection.request(
        packets.Tile.Get64(
            tile_index=tile_index,
            length=length,
            rect=TileBufferRect(fb_index=0, x=x, y=y, width=width),
        )
    )
    self._raise_if_unhandled(response)

    max_colors = device_chain[0].width * device_chain[0].height

    # Convert protocol colors to HSBK
    result = [
        HSBK.from_protocol(proto_color)
        for proto_color in response.colors[:max_colors]
    ]

    # Update state if it exists and we fetched all colors from tile 0
    if self._state is not None and hasattr(self._state, "tile_colors"):
        if tile_index == 0 and x == 0 and y == 0 and len(result) == max_colors:
            self._state.tile_colors = result
            self._state.last_updated = __import__("time").time()

    return result
```

##### get_all_tile_colors

```python
get_all_tile_colors() -> list[list[HSBK]]
```

Get colors for all tiles in the chain.

Fetches colors from each tile in the device chain and returns them as a list of color lists (one per tile). This is the matrix equivalent of MultiZoneLight's get_all_color_zones().

For tiles with >64 zones (e.g., 16x8 Ceiling with 128 zones), makes multiple Get64 requests to fetch all colors.

Always fetches from device. Tiles are queried sequentially to avoid overwhelming the device with concurrent requests.

| RETURNS            | DESCRIPTION                                                        |
| ------------------ | ------------------------------------------------------------------ |
| `list[list[HSBK]]` | List of color lists, one per tile. Each inner list contains        |
| `list[list[HSBK]]` | all colors for that tile (64 for 8x8 tiles, 128 for 16x8 Ceiling). |

| RAISES                        | DESCRIPTION                            |
| ----------------------------- | -------------------------------------- |
| `LifxDeviceNotFoundError`     | If device is not connected             |
| `LifxTimeoutError`            | If device does not respond             |
| `LifxUnsupportedCommandError` | If device doesn't support this command |

Example

```python
# Get colors for all tiles
all_colors = await matrix.get_all_tile_colors()
print(f"Device has {len(all_colors)} tiles")
for i, tile_colors in enumerate(all_colors):
    print(f"Tile {i}: {len(tile_colors)} colors")

# Flatten to single list if needed
flat_colors = [c for tile in all_colors for c in tile]
```

Source code in `src/lifx/devices/matrix.py`

````python
async def get_all_tile_colors(self) -> list[list[HSBK]]:
    """Get colors for all tiles in the chain.

    Fetches colors from each tile in the device chain and returns them
    as a list of color lists (one per tile). This is the matrix equivalent
    of MultiZoneLight's get_all_color_zones().

    For tiles with >64 zones (e.g., 16x8 Ceiling with 128 zones), makes
    multiple Get64 requests to fetch all colors.

    Always fetches from device. Tiles are queried sequentially to avoid
    overwhelming the device with concurrent requests.

    Returns:
        List of color lists, one per tile. Each inner list contains
        all colors for that tile (64 for 8x8 tiles, 128 for 16x8 Ceiling).

    Raises:
        LifxDeviceNotFoundError: If device is not connected
        LifxTimeoutError: If device does not respond
        LifxUnsupportedCommandError: If device doesn't support this command

    Example:
        ```python
        # Get colors for all tiles
        all_colors = await matrix.get_all_tile_colors()
        print(f"Device has {len(all_colors)} tiles")
        for i, tile_colors in enumerate(all_colors):
            print(f"Tile {i}: {len(tile_colors)} colors")

        # Flatten to single list if needed
        flat_colors = [c for tile in all_colors for c in tile]
        ```
    """
    # Get device chain (use cached if available)
    if self._device_chain is None:
        device_chain = await self.get_device_chain()
    else:
        device_chain = self._device_chain

    # Fetch colors from each tile sequentially
    all_colors: list[list[HSBK]] = []
    for tile in device_chain:
        tile_zone_count = tile.width * tile.height

        if tile_zone_count <= 64:
            # Single request for tiles with ≤64 zones
            tile_colors = await self.get64(tile_index=tile.tile_index)
            all_colors.append(tile_colors)
        else:
            # Multiple requests for tiles with >64 zones (e.g., 16x8 Ceiling)
            # Split into multiple 64-zone requests by row
            tile_colors = []
            rows_per_request = 64 // tile.width  # e.g., 64/16 = 4 rows

            for y_offset in range(0, tile.height, rows_per_request):
                chunk = await self.get64(
                    tile_index=tile.tile_index,
                    x=0,
                    y=y_offset,
                    width=tile.width,
                )
                tile_colors.extend(chunk)

            all_colors.append(tile_colors)

    # Update state if it exists (flatten for state storage)
    if self._state is not None and hasattr(self._state, "tile_colors"):
        flat_colors = [c for tile_colors in all_colors for c in tile_colors]
        self._state.tile_colors = flat_colors
        self._state.last_updated = time.time()

    return all_colors
````

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
    tile_index: int,
    source_fb: int = 1,
    target_fb: int = 0,
    duration: float = 0.0,
) -> None
```

Copy frame buffer (for tiles with >64 zones).

This is used for tiles with more than 64 zones. After setting colors in the temporary buffer (fb=1), copy to the display buffer (fb=0).

| PARAMETER    | DESCRIPTION                                                                          |
| ------------ | ------------------------------------------------------------------------------------ |
| `tile_index` | Index of the tile (0-based) **TYPE:** `int`                                          |
| `source_fb`  | Source frame buffer index (usually 1) **TYPE:** `int` **DEFAULT:** `1`               |
| `target_fb`  | Target frame buffer index (usually 0) **TYPE:** `int` **DEFAULT:** `0`               |
| `duration`   | time in seconds to transition if target_fb is 0 **TYPE:** `float` **DEFAULT:** `0.0` |

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
> > > await matrix.copy_frame_buffer( ... tile_index=0, source_fb=1, target_fb=0, duration=2.0 ... )

Source code in `src/lifx/devices/matrix.py`

```python
async def copy_frame_buffer(
    self,
    tile_index: int,
    source_fb: int = 1,
    target_fb: int = 0,
    duration: float = 0.0,
) -> None:
    """Copy frame buffer (for tiles with >64 zones).

    This is used for tiles with more than 64 zones. After setting colors
    in the temporary buffer (fb=1), copy to the display buffer (fb=0).

    Args:
        tile_index: Index of the tile (0-based)
        source_fb: Source frame buffer index (usually 1)
        target_fb: Target frame buffer index (usually 0)
        duration: time in seconds to transition if target_fb is 0

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
        >>> await matrix.copy_frame_buffer(
        ...     tile_index=0, source_fb=1, target_fb=0, duration=2.0
        ... )
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
    duration_ms = round(duration * 1000 if duration else 0)

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
            duration=duration_ms,
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

##### get_effect

```python
get_effect() -> MatrixEffect
```

Get current running matrix effect.

| RETURNS        | DESCRIPTION                                      |
| -------------- | ------------------------------------------------ |
| `MatrixEffect` | MatrixEffect describing the current effect state |

| RAISES                        | DESCRIPTION                            |
| ----------------------------- | -------------------------------------- |
| `LifxDeviceNotFoundError`     | If device is not connected             |
| `LifxTimeoutError`            | If device does not respond             |
| `LifxUnsupportedCommandError` | If device doesn't support this command |

Example

> > > effect = await matrix.get_effect() print(f"Effect type: {effect.effect_type}")

Source code in `src/lifx/devices/matrix.py`

```python
async def get_effect(self) -> MatrixEffect:
    """Get current running matrix effect.

    Returns:
        MatrixEffect describing the current effect state

    Raises:
        LifxDeviceNotFoundError: If device is not connected
        LifxTimeoutError: If device does not respond
        LifxUnsupportedCommandError: If device doesn't support this command

    Example:
        >>> effect = await matrix.get_effect()
        >>> print(f"Effect type: {effect.effect_type}")
    """
    _LOGGER.debug("Getting matrix effect for %s", self.label or self.serial)

    response: packets.Tile.StateEffect = await self.connection.request(
        packets.Tile.GetEffect()
    )
    self._raise_if_unhandled(response)

    # Convert protocol effect to MatrixEffect
    palette = [
        HSBK.from_protocol(proto_color)
        for proto_color in response.settings.palette[
            : response.settings.palette_count
        ]
    ]

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

    # Update state if it exists
    if self._state is not None and hasattr(self._state, "effect"):
        self._state.effect = effect.effect_type
        self._state.last_updated = __import__("time").time()

    return effect
```

##### set_effect

```python
set_effect(
    effect_type: FirmwareEffect,
    speed: float = 3.0,
    duration: int = 0,
    palette: list[HSBK] | None = None,
    sky_type: TileEffectSkyType = SUNRISE,
    cloud_saturation_min: int = 0,
    cloud_saturation_max: int = 0,
) -> None
```

Set matrix effect with configuration.

| PARAMETER              | DESCRIPTION                                                                                    |
| ---------------------- | ---------------------------------------------------------------------------------------------- |
| `effect_type`          | Type of effect (OFF, MORPH, FLAME, SKY) **TYPE:** `FirmwareEffect`                             |
| `speed`                | Effect speed in seconds (default: 3) **TYPE:** `float` **DEFAULT:** `3.0`                      |
| `duration`             | Total effect duration in nanoseconds (0 for infinite) **TYPE:** `int` **DEFAULT:** `0`         |
| `palette`              | Color palette for the effect (max 16 colors, None for no palette) **TYPE:** \`list[HSBK]       |
| `sky_type`             | Sky effect type (SUNRISE, SUNSET, CLOUDS) **TYPE:** `TileEffectSkyType` **DEFAULT:** `SUNRISE` |
| `cloud_saturation_min` | Minimum cloud saturation (0-255, for CLOUDS) **TYPE:** `int` **DEFAULT:** `0`                  |
| `cloud_saturation_max` | Maximum cloud saturation (0-255, for CLOUDS) **TYPE:** `int` **DEFAULT:** `0`                  |

Example

> > > ###### Set MORPH effect with rainbow palette
> > >
> > > rainbow = [ ... HSBK(0, 1.0, 1.0, 3500), # Red ... HSBK(60, 1.0, 1.0, 3500), # Yellow ... HSBK(120, 1.0, 1.0, 3500), # Green ... HSBK(240, 1.0, 1.0, 3500), # Blue ... ] await matrix.set_effect( ... effect_type=FirmwareEffect.MORPH, ... speed=5.0, ... palette=rainbow, ... )
> > >
> > > ###### Set effect without a palette
> > >
> > > await matrix.set_effect( ... effect_type=FirmwareEffect.FLAME, ... speed=3.0, ... )

Source code in `src/lifx/devices/matrix.py`

```python
async def set_effect(
    self,
    effect_type: FirmwareEffect,
    speed: float = 3.0,
    duration: int = 0,
    palette: list[HSBK] | None = None,
    sky_type: TileEffectSkyType = TileEffectSkyType.SUNRISE,
    cloud_saturation_min: int = 0,
    cloud_saturation_max: int = 0,
) -> None:
    """Set matrix effect with configuration.

    Args:
        effect_type: Type of effect (OFF, MORPH, FLAME, SKY)
        speed: Effect speed in seconds (default: 3)
        duration: Total effect duration in nanoseconds (0 for infinite)
        palette: Color palette for the effect (max 16 colors, None for no palette)
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
        >>> await matrix.set_effect(
        ...     effect_type=FirmwareEffect.MORPH,
        ...     speed=5.0,
        ...     palette=rainbow,
        ... )

        >>> # Set effect without a palette
        >>> await matrix.set_effect(
        ...     effect_type=FirmwareEffect.FLAME,
        ...     speed=3.0,
        ... )
    """
    _LOGGER.debug(
        "Setting matrix effect %s (speed=%d) for %s",
        effect_type,
        speed,
        self.label or self.serial,
    )
    speed_ms = round(speed * 1000) if speed else 3000

    # Create and validate MatrixEffect
    effect = MatrixEffect(
        effect_type=effect_type,
        speed=speed_ms,
        duration=duration,
        palette=palette,
        sky_type=sky_type,
        cloud_saturation_min=cloud_saturation_min,
        cloud_saturation_max=cloud_saturation_max,
    )

    # Convert to protocol format
    proto_palette = []
    palette_count = 0

    if effect.palette is not None:
        palette_count = len(effect.palette)
        for color in effect.palette:
            proto_palette.append(
                LightHsbk(
                    hue=int(color.hue / 360 * 65535),
                    saturation=int(color.saturation * 65535),
                    brightness=int(color.brightness * 65535),
                    kelvin=color.kelvin,
                )
            )

    # Pad palette to 16 colors (protocol requirement)
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
        palette_count=palette_count,
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
    theme: Theme,
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
        canvas.add_points_for_tile((int(tile.user_x), int(tile.user_y)), theme)

    # Shuffle and blur ONCE after all points are added
    # (Previously these were inside the loop, causing earlier tiles' points
    # to be shuffled/blurred multiple times, displacing them from their
    # intended positions and losing theme color variety)
    canvas.shuffle_points()
    canvas.blur_by_distance()

    # Create tile canvas and fill in gaps for smooth interpolation
    tile_canvas = Canvas()
    for tile in tiles:
        tile_canvas.fill_in_points(
            canvas,
            int(tile.user_x),
            int(tile.user_y),
            tile.width,
            tile.height,
        )

    # Final blur for smooth gradients
    tile_canvas.blur()

    # Check if light is on
    is_on = await self.get_power()

    # Apply colors to each tile
    for tile in tiles:
        # Extract tile colors from canvas as 1D list
        tile_coords = (int(tile.user_x), int(tile.user_y))
        colors = tile_canvas.points_for_tile(
            tile_coords, width=tile.width, height=tile.height
        )

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

##### refresh_state

```python
refresh_state() -> None
```

Refresh matrix light state from hardware.

Fetches color, tiles, tile colors for all tiles, and effect.

| RAISES                    | DESCRIPTION                       |
| ------------------------- | --------------------------------- |
| `RuntimeError`            | If state has not been initialized |
| `LifxTimeoutError`        | If device does not respond        |
| `LifxDeviceNotFoundError` | If device cannot be reached       |

Source code in `src/lifx/devices/matrix.py`

```python
async def refresh_state(self) -> None:
    """Refresh matrix light state from hardware.

    Fetches color, tiles, tile colors for all tiles, and effect.

    Raises:
        RuntimeError: If state has not been initialized
        LifxTimeoutError: If device does not respond
        LifxDeviceNotFoundError: If device cannot be reached
    """
    await super().refresh_state()

    # Fetch all matrix light state sequentially to avoid overwhelming device
    all_tile_colors = await self.get_all_tile_colors()
    effect = await self.get_effect()

    # Flatten tile colors for state storage
    self._state.tile_colors = [c for tile in all_tile_colors for c in tile]
    self._state.effect = effect.effect_type
```

## Ceiling Light

The `CeilingLight` class extends `MatrixLight` with independent control over uplight and downlight components for LIFX Ceiling fixtures.

### CeilingLight

```python
CeilingLight(
    serial: str,
    ip: str,
    port: int = 56700,
    timeout: float = 0.5,
    max_retries: int = 3,
    state_file: str | None = None,
)
```

Bases: `MatrixLight`

LIFX Ceiling Light with independent uplight and downlight control.

CeilingLight extends MatrixLight to provide semantic control over uplight and downlight components while maintaining full backward compatibility with the MatrixLight API.

The uplight component is the last zone in the matrix, and the downlight component consists of all other zones.

Example

```python
from lifx.devices import CeilingLight
from lifx.color import HSBK

async with await CeilingLight.from_ip("192.168.1.100") as ceiling:
    # Independent component control
    await ceiling.set_downlight_colors(HSBK(hue=0, sat=0, bri=1.0, kelvin=3500))
    await ceiling.set_uplight_color(HSBK(hue=30, sat=0.2, bri=0.3, kelvin=2700))

    # Turn components on/off
    await ceiling.turn_downlight_on()
    await ceiling.turn_uplight_off()

    # Check component state
    if ceiling.uplight_is_on:
        print("Uplight is on")
```

| PARAMETER     | DESCRIPTION                                                                                         |
| ------------- | --------------------------------------------------------------------------------------------------- |
| `serial`      | Device serial number **TYPE:** `str`                                                                |
| `ip`          | Device IP address **TYPE:** `str`                                                                   |
| `port`        | Device UDP port (default: 56700) **TYPE:** `int` **DEFAULT:** `56700`                               |
| `timeout`     | Overall timeout for network requests in seconds (default: 0.5) **TYPE:** `float` **DEFAULT:** `0.5` |
| `max_retries` | Maximum number of retry attempts for network requests (default: 3) **TYPE:** `int` **DEFAULT:** `3` |
| `state_file`  | Optional path to JSON file for state persistence **TYPE:** \`str                                    |

| RAISES      | DESCRIPTION                                  |
| ----------- | -------------------------------------------- |
| `LifxError` | If device is not a supported Ceiling product |

| METHOD                 | DESCRIPTION                                         |
| ---------------------- | --------------------------------------------------- |
| `refresh_state`        | Refresh ceiling light state from hardware.          |
| `from_ip`              | Create CeilingLight from IP address.                |
| `get_uplight_color`    | Get current uplight component color from device.    |
| `get_downlight_colors` | Get current downlight component colors from device. |
| `set_uplight_color`    | Set uplight component color.                        |
| `set_downlight_colors` | Set downlight component colors.                     |
| `turn_uplight_on`      | Turn uplight component on.                          |
| `turn_uplight_off`     | Turn uplight component off.                         |
| `turn_downlight_on`    | Turn downlight component on.                        |
| `turn_downlight_off`   | Turn downlight component off.                       |

| ATTRIBUTE         | DESCRIPTION                                                         |
| ----------------- | ------------------------------------------------------------------- |
| `state`           | Get Ceiling light state. **TYPE:** `CeilingLightState`              |
| `uplight_zone`    | Zone index of the uplight component. **TYPE:** `int`                |
| `downlight_zones` | Slice representing the downlight component zones. **TYPE:** `slice` |
| `uplight_is_on`   | True if uplight component is currently on. **TYPE:** `bool`         |
| `downlight_is_on` | True if downlight component is currently on. **TYPE:** `bool`       |

Source code in `src/lifx/devices/ceiling.py`

```python
def __init__(
    self,
    serial: str,
    ip: str,
    port: int = 56700,  # LIFX_UDP_PORT
    timeout: float = 0.5,  # DEFAULT_REQUEST_TIMEOUT
    max_retries: int = 3,  # DEFAULT_MAX_RETRIES
    state_file: str | None = None,
):
    """Initialize CeilingLight.

    Args:
        serial: Device serial number
        ip: Device IP address
        port: Device UDP port (default: 56700)
        timeout: Overall timeout for network requests in seconds
            (default: 0.5)
        max_retries: Maximum number of retry attempts for network requests
            (default: 3)
        state_file: Optional path to JSON file for state persistence

    Raises:
        LifxError: If device is not a supported Ceiling product
    """
    super().__init__(serial, ip, port, timeout, max_retries)
    self._state_file = state_file
    self._stored_uplight_state: HSBK | None = None
    self._stored_downlight_state: list[HSBK] | None = None
    self._last_uplight_color: HSBK | None = None
    self._last_downlight_colors: list[HSBK] | None = None
```

#### Attributes

##### state

```python
state: CeilingLightState
```

Get Ceiling light state.

| RETURNS             | DESCRIPTION                                       |
| ------------------- | ------------------------------------------------- |
| `CeilingLightState` | CeilingLightState with current state information. |

| RAISES         | DESCRIPTION                              |
| -------------- | ---------------------------------------- |
| `RuntimeError` | If accessed before state initialization. |

##### uplight_zone

```python
uplight_zone: int
```

Zone index of the uplight component.

| RETURNS | DESCRIPTION                                           |
| ------- | ----------------------------------------------------- |
| `int`   | Zone index (63 for standard Ceiling, 127 for Capsule) |

| RAISES      | DESCRIPTION                                                 |
| ----------- | ----------------------------------------------------------- |
| `LifxError` | If device version is not available or not a Ceiling product |

##### downlight_zones

```python
downlight_zones: slice
```

Slice representing the downlight component zones.

| RETURNS | DESCRIPTION                                                         |
| ------- | ------------------------------------------------------------------- |
| `slice` | Slice object (slice(0, 63) for standard, slice(0, 127) for Capsule) |

| RAISES      | DESCRIPTION                                                 |
| ----------- | ----------------------------------------------------------- |
| `LifxError` | If device version is not available or not a Ceiling product |

##### uplight_is_on

```python
uplight_is_on: bool
```

True if uplight component is currently on.

Calculated as: power_level > 0 AND uplight brightness > 0

Note

Requires recent data from device. Call get_uplight_color() or get_power() to refresh cached values before checking this property.

| RETURNS | DESCRIPTION                                      |
| ------- | ------------------------------------------------ |
| `bool`  | True if uplight component is on, False otherwise |

##### downlight_is_on

```python
downlight_is_on: bool
```

True if downlight component is currently on.

Calculated as: power_level > 0 AND NOT all downlight zones have brightness == 0

Note

Requires recent data from device. Call get_downlight_colors() or get_power() to refresh cached values before checking this property.

| RETURNS | DESCRIPTION                                        |
| ------- | -------------------------------------------------- |
| `bool`  | True if downlight component is on, False otherwise |

#### Functions

##### refresh_state

```python
refresh_state() -> None
```

Refresh ceiling light state from hardware.

Fetches color, tiles, tile colors, effect, and ceiling component state.

| RAISES                    | DESCRIPTION                       |
| ------------------------- | --------------------------------- |
| `RuntimeError`            | If state has not been initialized |
| `LifxTimeoutError`        | If device does not respond        |
| `LifxDeviceNotFoundError` | If device cannot be reached       |

Source code in `src/lifx/devices/ceiling.py`

```python
async def refresh_state(self) -> None:
    """Refresh ceiling light state from hardware.

    Fetches color, tiles, tile colors, effect, and ceiling component state.

    Raises:
        RuntimeError: If state has not been initialized
        LifxTimeoutError: If device does not respond
        LifxDeviceNotFoundError: If device cannot be reached
    """
    await super().refresh_state()

    # Get ceiling component colors
    uplight_color = await self.get_uplight_color()
    downlight_colors = await self.get_downlight_colors()

    # Update ceiling-specific state fields
    state = cast(CeilingLightState, self._state)
    state.uplight_color = uplight_color
    state.downlight_colors = downlight_colors
    state.uplight_is_on = bool(
        self.state.power > 0 and uplight_color.brightness > 0
    )
    state.downlight_is_on = bool(
        self.state.power > 0 and any(c.brightness > 0 for c in downlight_colors)
    )
```

##### from_ip

```python
from_ip(
    ip: str,
    port: int = 56700,
    serial: str | None = None,
    timeout: float = 0.5,
    max_retries: int = 3,
    *,
    state_file: str | None = None,
) -> CeilingLight
```

Create CeilingLight from IP address.

| PARAMETER     | DESCRIPTION                                                                   |
| ------------- | ----------------------------------------------------------------------------- |
| `ip`          | Device IP address **TYPE:** `str`                                             |
| `port`        | Port number (default LIFX_UDP_PORT) **TYPE:** `int` **DEFAULT:** `56700`      |
| `serial`      | Serial number as 12-digit hex string **TYPE:** \`str                          |
| `timeout`     | Request timeout for this device instance **TYPE:** `float` **DEFAULT:** `0.5` |
| `max_retries` | Maximum number of retries for requests **TYPE:** `int` **DEFAULT:** `3`       |
| `state_file`  | Optional path to JSON file for state persistence **TYPE:** \`str              |

| RETURNS        | DESCRIPTION           |
| -------------- | --------------------- |
| `CeilingLight` | CeilingLight instance |

| RAISES                    | DESCRIPTION                               |
| ------------------------- | ----------------------------------------- |
| `LifxDeviceNotFoundError` | Device not found at IP                    |
| `LifxTimeoutError`        | Device did not respond                    |
| `LifxError`               | Device is not a supported Ceiling product |

Source code in `src/lifx/devices/ceiling.py`

```python
@classmethod
async def from_ip(
    cls,
    ip: str,
    port: int = 56700,  # LIFX_UDP_PORT
    serial: str | None = None,
    timeout: float = 0.5,  # DEFAULT_REQUEST_TIMEOUT
    max_retries: int = 3,  # DEFAULT_MAX_RETRIES
    *,
    state_file: str | None = None,
) -> CeilingLight:
    """Create CeilingLight from IP address.

    Args:
        ip: Device IP address
        port: Port number (default LIFX_UDP_PORT)
        serial: Serial number as 12-digit hex string
        timeout: Request timeout for this device instance
        max_retries: Maximum number of retries for requests
        state_file: Optional path to JSON file for state persistence

    Returns:
        CeilingLight instance

    Raises:
        LifxDeviceNotFoundError: Device not found at IP
        LifxTimeoutError: Device did not respond
        LifxError: Device is not a supported Ceiling product
    """
    # Use parent class factory method
    device = await super().from_ip(ip, port, serial, timeout, max_retries)
    # Type cast to CeilingLight and set state_file
    ceiling = CeilingLight(device.serial, device.ip)
    ceiling._state_file = state_file
    ceiling.connection = device.connection
    return ceiling
```

##### get_uplight_color

```python
get_uplight_color() -> HSBK
```

Get current uplight component color from device.

| RETURNS | DESCRIPTION                |
| ------- | -------------------------- |
| `HSBK`  | HSBK color of uplight zone |

| RAISES             | DESCRIPTION            |
| ------------------ | ---------------------- |
| `LifxTimeoutError` | Device did not respond |

Source code in `src/lifx/devices/ceiling.py`

```python
async def get_uplight_color(self) -> HSBK:
    """Get current uplight component color from device.

    Returns:
        HSBK color of uplight zone

    Raises:
        LifxTimeoutError: Device did not respond
    """
    # Get all colors from tile
    all_colors = await self.get_all_tile_colors()
    tile_colors = all_colors[0]  # First tile

    # Extract uplight zone
    uplight_color = tile_colors[self.uplight_zone]

    # Cache for is_on property
    self._last_uplight_color = uplight_color

    return uplight_color
```

##### get_downlight_colors

```python
get_downlight_colors() -> list[HSBK]
```

Get current downlight component colors from device.

| RETURNS      | DESCRIPTION                                                   |
| ------------ | ------------------------------------------------------------- |
| `list[HSBK]` | List of HSBK colors for each downlight zone (63 or 127 zones) |

| RAISES             | DESCRIPTION            |
| ------------------ | ---------------------- |
| `LifxTimeoutError` | Device did not respond |

Source code in `src/lifx/devices/ceiling.py`

```python
async def get_downlight_colors(self) -> list[HSBK]:
    """Get current downlight component colors from device.

    Returns:
        List of HSBK colors for each downlight zone (63 or 127 zones)

    Raises:
        LifxTimeoutError: Device did not respond
    """
    # Get all colors from tile
    all_colors = await self.get_all_tile_colors()
    tile_colors = all_colors[0]  # First tile

    # Extract downlight zones
    downlight_colors = tile_colors[self.downlight_zones]

    # Cache for is_on property
    self._last_downlight_colors = downlight_colors

    return downlight_colors
```

##### set_uplight_color

```python
set_uplight_color(color: HSBK, duration: float = 0.0) -> None
```

Set uplight component color.

| PARAMETER  | DESCRIPTION                                                                       |
| ---------- | --------------------------------------------------------------------------------- |
| `color`    | HSBK color to set **TYPE:** `HSBK`                                                |
| `duration` | Transition duration in seconds (default 0.0) **TYPE:** `float` **DEFAULT:** `0.0` |

| RAISES             | DESCRIPTION                                             |
| ------------------ | ------------------------------------------------------- |
| `ValueError`       | If color.brightness == 0 (use turn_uplight_off instead) |
| `LifxTimeoutError` | Device did not respond                                  |

Note

Also updates stored state for future restoration.

Source code in `src/lifx/devices/ceiling.py`

```python
async def set_uplight_color(self, color: HSBK, duration: float = 0.0) -> None:
    """Set uplight component color.

    Args:
        color: HSBK color to set
        duration: Transition duration in seconds (default 0.0)

    Raises:
        ValueError: If color.brightness == 0 (use turn_uplight_off instead)
        LifxTimeoutError: Device did not respond

    Note:
        Also updates stored state for future restoration.
    """
    if color.brightness == 0:
        raise ValueError(
            "Cannot set uplight color with brightness=0. "
            "Use turn_uplight_off() instead."
        )

    # Get current colors for all zones
    all_colors = await self.get_all_tile_colors()
    tile_colors = all_colors[0]

    # Update uplight zone
    tile_colors[self.uplight_zone] = color

    # Set all colors back (duration in milliseconds for set_matrix_colors)
    await self.set_matrix_colors(0, tile_colors, duration=int(duration * 1000))

    # Store state
    self._stored_uplight_state = color
    self._last_uplight_color = color

    # Persist if enabled
    if self._state_file:
        self._save_state_to_file()
```

##### set_downlight_colors

```python
set_downlight_colors(colors: HSBK | list[HSBK], duration: float = 0.0) -> None
```

Set downlight component colors.

| PARAMETER  | DESCRIPTION                                                                                                                                        |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `colors`   | Either: - Single HSBK: sets all downlight zones to same color - List\[HSBK\]: sets each zone individually (must match zone count) **TYPE:** \`HSBK |
| `duration` | Transition duration in seconds (default 0.0) **TYPE:** `float` **DEFAULT:** `0.0`                                                                  |

| RAISES             | DESCRIPTION                                                   |
| ------------------ | ------------------------------------------------------------- |
| `ValueError`       | If any color.brightness == 0 (use turn_downlight_off instead) |
| `ValueError`       | If list length doesn't match downlight zone count             |
| `LifxTimeoutError` | Device did not respond                                        |

Note

Also updates stored state for future restoration.

Source code in `src/lifx/devices/ceiling.py`

```python
async def set_downlight_colors(
    self, colors: HSBK | list[HSBK], duration: float = 0.0
) -> None:
    """Set downlight component colors.

    Args:
        colors: Either:
            - Single HSBK: sets all downlight zones to same color
            - List[HSBK]: sets each zone individually (must match zone count)
        duration: Transition duration in seconds (default 0.0)

    Raises:
        ValueError: If any color.brightness == 0 (use turn_downlight_off instead)
        ValueError: If list length doesn't match downlight zone count
        LifxTimeoutError: Device did not respond

    Note:
        Also updates stored state for future restoration.
    """
    # Validate and normalize colors
    if isinstance(colors, HSBK):
        if colors.brightness == 0:
            raise ValueError(
                "Cannot set downlight color with brightness=0. "
                "Use turn_downlight_off() instead."
            )
        downlight_colors = [colors] * len(range(*self.downlight_zones.indices(256)))
    else:
        if all(c.brightness == 0 for c in colors):
            raise ValueError(
                "Cannot set downlight colors with brightness=0. "
                "Use turn_downlight_off() instead."
            )

        expected_count = len(range(*self.downlight_zones.indices(256)))
        if len(colors) != expected_count:
            raise ValueError(
                f"Expected {expected_count} colors for downlight, got {len(colors)}"
            )
        downlight_colors = colors

    # Get current colors for all zones
    all_colors = await self.get_all_tile_colors()
    tile_colors = all_colors[0]

    # Update downlight zones
    tile_colors[self.downlight_zones] = downlight_colors

    # Set all colors back
    await self.set_matrix_colors(0, tile_colors, duration=int(duration * 1000))

    # Store state
    self._stored_downlight_state = downlight_colors
    self._last_downlight_colors = downlight_colors

    # Persist if enabled
    if self._state_file:
        self._save_state_to_file()
```

##### turn_uplight_on

```python
turn_uplight_on(color: HSBK | None = None, duration: float = 0.0) -> None
```

Turn uplight component on.

| PARAMETER  | DESCRIPTION                                                                                                                                          |
| ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| `color`    | Optional HSBK color. If provided: - Uses this color immediately - Updates stored state If None, uses brightness determination logic **TYPE:** \`HSBK |
| `duration` | Transition duration in seconds (default 0.0) **TYPE:** `float` **DEFAULT:** `0.0`                                                                    |

| RAISES             | DESCRIPTION              |
| ------------------ | ------------------------ |
| `ValueError`       | If color.brightness == 0 |
| `LifxTimeoutError` | Device did not respond   |

Source code in `src/lifx/devices/ceiling.py`

```python
async def turn_uplight_on(
    self, color: HSBK | None = None, duration: float = 0.0
) -> None:
    """Turn uplight component on.

    Args:
        color: Optional HSBK color. If provided:
            - Uses this color immediately
            - Updates stored state
            If None, uses brightness determination logic
        duration: Transition duration in seconds (default 0.0)

    Raises:
        ValueError: If color.brightness == 0
        LifxTimeoutError: Device did not respond
    """
    if color is not None:
        if color.brightness == 0:
            raise ValueError("Cannot turn on uplight with brightness=0")
        await self.set_uplight_color(color, duration)
    else:
        # Determine color using priority logic
        determined_color = await self._determine_uplight_brightness()
        await self.set_uplight_color(determined_color, duration)
```

##### turn_uplight_off

```python
turn_uplight_off(color: HSBK | None = None, duration: float = 0.0) -> None
```

Turn uplight component off.

| PARAMETER  | DESCRIPTION                                                                                                                                                                                       |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `color`    | Optional HSBK color to store for future turn_on. If provided, stores this color (with brightness=0 on the device). If None, stores current color from device before turning off. **TYPE:** \`HSBK |
| `duration` | Transition duration in seconds (default 0.0) **TYPE:** `float` **DEFAULT:** `0.0`                                                                                                                 |

| RAISES             | DESCRIPTION              |
| ------------------ | ------------------------ |
| `ValueError`       | If color.brightness == 0 |
| `LifxTimeoutError` | Device did not respond   |

Note

Sets uplight zone brightness to 0 on device while preserving H, S, K.

Source code in `src/lifx/devices/ceiling.py`

```python
async def turn_uplight_off(
    self, color: HSBK | None = None, duration: float = 0.0
) -> None:
    """Turn uplight component off.

    Args:
        color: Optional HSBK color to store for future turn_on.
            If provided, stores this color (with brightness=0 on the device).
            If None, stores current color from device before turning off.
        duration: Transition duration in seconds (default 0.0)

    Raises:
        ValueError: If color.brightness == 0
        LifxTimeoutError: Device did not respond

    Note:
        Sets uplight zone brightness to 0 on device while preserving H, S, K.
    """
    if color is not None:
        if color.brightness == 0:
            raise ValueError(
                "Provided color cannot have brightness=0. "
                "Omit the parameter to use current color."
            )
        # Store the provided color
        self._stored_uplight_state = color
    else:
        # Get and store current color
        current_color = await self.get_uplight_color()
        self._stored_uplight_state = current_color

    # Create color with brightness=0 for device
    off_color = HSBK(
        hue=self._stored_uplight_state.hue,
        saturation=self._stored_uplight_state.saturation,
        brightness=0.0,
        kelvin=self._stored_uplight_state.kelvin,
    )

    # Get all colors and update uplight zone
    all_colors = await self.get_all_tile_colors()
    tile_colors = all_colors[0]
    tile_colors[self.uplight_zone] = off_color
    await self.set_matrix_colors(0, tile_colors, duration=int(duration * 1000))

    # Update cache
    self._last_uplight_color = off_color

    # Persist if enabled
    if self._state_file:
        self._save_state_to_file()
```

##### turn_downlight_on

```python
turn_downlight_on(
    colors: HSBK | list[HSBK] | None = None, duration: float = 0.0
) -> None
```

Turn downlight component on.

| PARAMETER  | DESCRIPTION                                                                                                                                                                                                                                        |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `colors`   | Optional colors. Can be: - None: uses brightness determination logic - Single HSBK: sets all downlight zones to same color - List\[HSBK\]: sets each zone individually (must match zone count) If provided, updates stored state. **TYPE:** \`HSBK |
| `duration` | Transition duration in seconds (default 0.0) **TYPE:** `float` **DEFAULT:** `0.0`                                                                                                                                                                  |

| RAISES             | DESCRIPTION                                       |
| ------------------ | ------------------------------------------------- |
| `ValueError`       | If any color.brightness == 0                      |
| `ValueError`       | If list length doesn't match downlight zone count |
| `LifxTimeoutError` | Device did not respond                            |

Source code in `src/lifx/devices/ceiling.py`

```python
async def turn_downlight_on(
    self, colors: HSBK | list[HSBK] | None = None, duration: float = 0.0
) -> None:
    """Turn downlight component on.

    Args:
        colors: Optional colors. Can be:
            - None: uses brightness determination logic
            - Single HSBK: sets all downlight zones to same color
            - List[HSBK]: sets each zone individually (must match zone count)
            If provided, updates stored state.
        duration: Transition duration in seconds (default 0.0)

    Raises:
        ValueError: If any color.brightness == 0
        ValueError: If list length doesn't match downlight zone count
        LifxTimeoutError: Device did not respond
    """
    if colors is not None:
        await self.set_downlight_colors(colors, duration)
    else:
        # Determine colors using priority logic
        determined_colors = await self._determine_downlight_brightness()
        await self.set_downlight_colors(determined_colors, duration)
```

##### turn_downlight_off

```python
turn_downlight_off(
    colors: HSBK | list[HSBK] | None = None, duration: float = 0.0
) -> None
```

Turn downlight component off.

| PARAMETER  | DESCRIPTION                                                                                                                                                                                                                                                                                     |
| ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `colors`   | Optional colors to store for future turn_on. Can be: - None: stores current colors from device - Single HSBK: stores this color for all zones - List\[HSBK\]: stores individual colors (must match zone count) If provided, stores these colors (with brightness=0 on device). **TYPE:** \`HSBK |
| `duration` | Transition duration in seconds (default 0.0) **TYPE:** `float` **DEFAULT:** `0.0`                                                                                                                                                                                                               |

| RAISES             | DESCRIPTION                                       |
| ------------------ | ------------------------------------------------- |
| `ValueError`       | If any color.brightness == 0                      |
| `ValueError`       | If list length doesn't match downlight zone count |
| `LifxTimeoutError` | Device did not respond                            |

Note

Sets all downlight zone brightness to 0 on device while preserving H, S, K.

Source code in `src/lifx/devices/ceiling.py`

```python
async def turn_downlight_off(
    self, colors: HSBK | list[HSBK] | None = None, duration: float = 0.0
) -> None:
    """Turn downlight component off.

    Args:
        colors: Optional colors to store for future turn_on. Can be:
            - None: stores current colors from device
            - Single HSBK: stores this color for all zones
            - List[HSBK]: stores individual colors (must match zone count)
            If provided, stores these colors (with brightness=0 on device).
        duration: Transition duration in seconds (default 0.0)

    Raises:
        ValueError: If any color.brightness == 0
        ValueError: If list length doesn't match downlight zone count
        LifxTimeoutError: Device did not respond

    Note:
        Sets all downlight zone brightness to 0 on device while preserving H, S, K.
    """
    expected_count = len(range(*self.downlight_zones.indices(256)))

    if colors is not None:
        # Validate and normalize provided colors
        if isinstance(colors, HSBK):
            if colors.brightness == 0:
                raise ValueError(
                    "Provided color cannot have brightness=0. "
                    "Omit the parameter to use current colors."
                )
            colors_to_store = [colors] * expected_count
        else:
            if all(c.brightness == 0 for c in colors):
                raise ValueError(
                    "Provided colors cannot have brightness=0. "
                    "Omit the parameter to use current colors."
                )
            if len(colors) != expected_count:
                raise ValueError(
                    f"Expected {expected_count} colors for downlight, "
                    f"got {len(colors)}"
                )
            colors_to_store = colors

        self._stored_downlight_state = colors_to_store
    else:
        # Get and store current colors
        current_colors = await self.get_downlight_colors()
        self._stored_downlight_state = current_colors

    # Create colors with brightness=0 for device
    off_colors = [
        HSBK(
            hue=c.hue,
            saturation=c.saturation,
            brightness=0.0,
            kelvin=c.kelvin,
        )
        for c in self._stored_downlight_state
    ]

    # Get all colors and update downlight zones
    all_colors = await self.get_all_tile_colors()
    tile_colors = all_colors[0]
    tile_colors[self.downlight_zones] = off_colors
    await self.set_matrix_colors(0, tile_colors, duration=int(duration * 1000))

    # Update cache
    self._last_downlight_colors = off_colors

    # Persist if enabled
    if self._state_file:
        self._save_state_to_file()
```

### CeilingLightState

The `CeilingLightState` dataclass extends `MatrixLightState` with ceiling-specific component information. It is returned by `CeilingLight.state` after connecting to a device.

#### CeilingLightState

```python
CeilingLightState(
    model: str,
    label: str,
    serial: str,
    mac_address: str,
    capabilities: DeviceCapabilities,
    power: int,
    host_firmware: FirmwareInfo,
    wifi_firmware: FirmwareInfo,
    location: CollectionInfo,
    group: CollectionInfo,
    last_updated: float,
    color: HSBK,
    chain: list[TileInfo],
    tile_orientations: dict[int, str],
    tile_colors: list[HSBK],
    tile_count: int,
    effect: FirmwareEffect,
    uplight_color: HSBK,
    downlight_colors: list[HSBK],
    uplight_is_on: bool,
    downlight_is_on: bool,
    uplight_zone: int,
    downlight_zones: slice,
)
```

Bases: `MatrixLightState`

Ceiling light device state with uplight/downlight component control.

Extends MatrixLightState with ceiling-specific component information.

| ATTRIBUTE          | DESCRIPTION                                                                  |
| ------------------ | ---------------------------------------------------------------------------- |
| `uplight_color`    | Current HSBK color of the uplight component **TYPE:** `HSBK`                 |
| `downlight_colors` | List of HSBK colors for each downlight zone **TYPE:** `list[HSBK]`           |
| `uplight_is_on`    | Whether uplight component is on (brightness > 0) **TYPE:** `bool`            |
| `downlight_is_on`  | Whether downlight component is on (any zone brightness > 0) **TYPE:** `bool` |
| `uplight_zone`     | Zone index for the uplight component **TYPE:** `int`                         |
| `downlight_zones`  | Slice representing downlight component zones **TYPE:** `slice`               |

| METHOD              | DESCRIPTION                                     |
| ------------------- | ----------------------------------------------- |
| `from_matrix_state` | Create CeilingLightState from MatrixLightState. |

##### Attributes

###### as_dict

```python
as_dict: Any
```

Return CeilingLightState as dict.

##### Functions

###### from_matrix_state

```python
from_matrix_state(
    matrix_state: MatrixLightState,
    uplight_color: HSBK,
    downlight_colors: list[HSBK],
    uplight_zone: int,
    downlight_zones: slice,
) -> CeilingLightState
```

Create CeilingLightState from MatrixLightState.

| PARAMETER          | DESCRIPTION                                                    |
| ------------------ | -------------------------------------------------------------- |
| `matrix_state`     | Base MatrixLightState to extend **TYPE:** `MatrixLightState`   |
| `uplight_color`    | Current uplight zone color **TYPE:** `HSBK`                    |
| `downlight_colors` | Current downlight zone colors **TYPE:** `list[HSBK]`           |
| `uplight_zone`     | Zone index for uplight component **TYPE:** `int`               |
| `downlight_zones`  | Slice representing downlight component zones **TYPE:** `slice` |

| RETURNS             | DESCRIPTION                                                     |
| ------------------- | --------------------------------------------------------------- |
| `CeilingLightState` | CeilingLightState with all matrix state plus ceiling components |

Source code in `src/lifx/devices/ceiling.py`

```python
@classmethod
def from_matrix_state(
    cls,
    matrix_state: MatrixLightState,
    uplight_color: HSBK,
    downlight_colors: list[HSBK],
    uplight_zone: int,
    downlight_zones: slice,
) -> CeilingLightState:
    """Create CeilingLightState from MatrixLightState.

    Args:
        matrix_state: Base MatrixLightState to extend
        uplight_color: Current uplight zone color
        downlight_colors: Current downlight zone colors
        uplight_zone: Zone index for uplight component
        downlight_zones: Slice representing downlight component zones

    Returns:
        CeilingLightState with all matrix state plus ceiling components
    """
    return cls(
        model=matrix_state.model,
        label=matrix_state.label,
        serial=matrix_state.serial,
        mac_address=matrix_state.mac_address,
        power=matrix_state.power,
        capabilities=matrix_state.capabilities,
        host_firmware=matrix_state.host_firmware,
        wifi_firmware=matrix_state.wifi_firmware,
        location=matrix_state.location,
        group=matrix_state.group,
        color=matrix_state.color,
        chain=matrix_state.chain,
        tile_orientations=matrix_state.tile_orientations,
        tile_colors=matrix_state.tile_colors,
        tile_count=matrix_state.tile_count,
        effect=matrix_state.effect,
        uplight_color=uplight_color,
        downlight_colors=downlight_colors,
        uplight_is_on=uplight_color.brightness > 0,
        downlight_is_on=any(c.brightness > 0 for c in downlight_colors),
        uplight_zone=uplight_zone,
        downlight_zones=downlight_zones,
        last_updated=time.time(),
    )
```

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

### Ambient Light Sensor

Light devices with ambient light sensors can measure the current ambient light level in lux:

```python
from lifx import Light


async def main():
    async with await Light.from_ip("192.168.1.100") as light:
        # Ensure light is off for accurate reading
        await light.set_power(False)

        # Get ambient light level in lux
        lux = await light.get_ambient_light_level()
        if lux > 0:
            print(f"Ambient light: {lux} lux")
        else:
            print("No ambient light sensor or completely dark")
```

**Notes:**

- Devices without ambient light sensors return 0.0 (not an error)
- For accurate readings, the light should be turned off (otherwise the light's own illumination interferes with the sensor)
- This is a volatile property - always fetched fresh from the device
- A reading of 0.0 could mean either no sensor or complete darkness
- Returns ambient light level in lux (higher values indicate brighter ambient light)

### MultiZone Control

```python
from lifx import MultiZoneLight, Colors, FirmwareEffect, Direction


async def main():
    async with await MultiZoneLight.from_ip("192.168.1.100") as light:
        # Get all zones - automatically uses best method
        colors = await light.get_all_color_zones()
        print(f"Device has {len(colors)} zones")

        # Set a MOVE effect
        await light.set_effect(
            effect_type=FirmwareEffect.MOVE,
            speed=5.0,  # seconds per cycle
            direction=Direction.FORWARD,
        )

        # Get current effect
        effect = await light.get_effect()
        print(f"Effect: {effect.effect_type.name}")
        if effect.effect_type == FirmwareEffect.MOVE:
            print(f"Direction: {effect.direction.name}")

        # Stop the effect
        await light.set_effect(effect_type=FirmwareEffect.OFF)
```

### Tile Control

```python
from lifx import MatrixLight, HSBK, FirmwareEffect


async def main():
    async with await MatrixLight.from_ip("192.168.1.100") as light:
        # Set a gradient across the tile
        colors = [
            HSBK(hue=h, saturation=1.0, brightness=0.5, kelvin=3500)
            for h in range(0, 360, 10)
        ]
        await light.set_tile_colors(colors)

        # Set a tile effect (MORPH, FLAME, or SKY)
        await light.set_effect(
            effect_type=FirmwareEffect.FLAME,
            speed=5.0,  # seconds per cycle
        )

        # Get current effect
        effect = await light.get_effect()
        print(f"Tile effect: {effect.effect_type.name}")

        # Stop the effect
        await light.set_effect(effect_type=FirmwareEffect.OFF)
```

### Ceiling Light Control

```python
from lifx import CeilingLight, HSBK


async def main():
    async with await CeilingLight.from_ip("192.168.1.100") as ceiling:
        # Set downlight to warm white
        await ceiling.set_downlight_colors(
            HSBK(hue=0, saturation=0, brightness=0.8, kelvin=3000)
        )

        # Set uplight to a dim ambient glow
        await ceiling.set_uplight_color(
            HSBK(hue=30, saturation=0.2, brightness=0.3, kelvin=2700)
        )

        # Turn uplight off (stores color for later restoration)
        await ceiling.turn_uplight_off()

        # Turn uplight back on (restores previous color)
        await ceiling.turn_uplight_on()

        # Check component state
        if ceiling.downlight_is_on:
            print("Downlight is currently on")
```

For detailed CeilingLight usage, see the [Ceiling Lights User Guide](https://djelibeybi.github.io/lifx-async/user-guide/ceiling-lights/index.md).
