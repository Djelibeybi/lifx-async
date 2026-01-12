# High-Level API

The high-level API provides simplified functions for common LIFX operations. These are the recommended entry points for most users.

## Discovery Functions

### discover

```python
discover(
    timeout: float = DISCOVERY_TIMEOUT,
    broadcast_address: str = "255.255.255.255",
    port: int = LIFX_UDP_PORT,
    max_response_time: float = MAX_RESPONSE_TIME,
    idle_timeout_multiplier: float = IDLE_TIMEOUT_MULTIPLIER,
    device_timeout: float = DEFAULT_REQUEST_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> AsyncGenerator[Device, None]
```

Discover LIFX devices and yield them as they are found.

| PARAMETER                 | DESCRIPTION                                                                                           |
| ------------------------- | ----------------------------------------------------------------------------------------------------- |
| `timeout`                 | Discovery timeout in seconds (default 3.0) **TYPE:** `float` **DEFAULT:** `DISCOVERY_TIMEOUT`         |
| `broadcast_address`       | Broadcast address to use (default "255.255.255.255") **TYPE:** `str` **DEFAULT:** `'255.255.255.255'` |
| `port`                    | Port to use (default LIFX_UDP_PORT) **TYPE:** `int` **DEFAULT:** `LIFX_UDP_PORT`                      |
| `max_response_time`       | Max time to wait for responses **TYPE:** `float` **DEFAULT:** `MAX_RESPONSE_TIME`                     |
| `idle_timeout_multiplier` | Idle timeout multiplier **TYPE:** `float` **DEFAULT:** `IDLE_TIMEOUT_MULTIPLIER`                      |
| `device_timeout`          | request timeout set on discovered devices **TYPE:** `float` **DEFAULT:** `DEFAULT_REQUEST_TIMEOUT`    |
| `max_retries`             | max retries per request set on discovered devices **TYPE:** `int` **DEFAULT:** `DEFAULT_MAX_RETRIES`  |

Yields: Device instances as they are discovered

Example

```python
# Process devices as they're discovered
async for device in discover():
    print(f"Found: {device.serial}")
    async with device:
        await device.set_power(True)

# Or collect all devices first
devices = []
async for device in discover():
    devices.append(device)
```

Source code in `src/lifx/api.py`

````python
async def discover(
    timeout: float = DISCOVERY_TIMEOUT,
    broadcast_address: str = "255.255.255.255",
    port: int = LIFX_UDP_PORT,
    max_response_time: float = MAX_RESPONSE_TIME,
    idle_timeout_multiplier: float = IDLE_TIMEOUT_MULTIPLIER,
    device_timeout: float = DEFAULT_REQUEST_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> AsyncGenerator[Device, None]:
    """Discover LIFX devices and yield them as they are found.

    Args:
        timeout: Discovery timeout in seconds (default 3.0)
        broadcast_address: Broadcast address to use (default "255.255.255.255")
        port: Port to use (default LIFX_UDP_PORT)
        max_response_time: Max time to wait for responses
        idle_timeout_multiplier: Idle timeout multiplier
        device_timeout: request timeout set on discovered devices
        max_retries: max retries per request set on discovered devices
    Yields:
        Device instances as they are discovered

    Example:
        ```python
        # Process devices as they're discovered
        async for device in discover():
            print(f"Found: {device.serial}")
            async with device:
                await device.set_power(True)

        # Or collect all devices first
        devices = []
        async for device in discover():
            devices.append(device)
        ```
    """
    async for discovered in discover_devices(
        timeout=timeout,
        broadcast_address=broadcast_address,
        port=port,
        max_response_time=max_response_time,
        idle_timeout_multiplier=idle_timeout_multiplier,
        device_timeout=device_timeout,
        max_retries=max_retries,
    ):
        device = await discovered.create_device()
        if device is not None:
            yield device
````

### find_by_serial

```python
find_by_serial(
    serial: str,
    timeout: float = DISCOVERY_TIMEOUT,
    broadcast_address: str = "255.255.255.255",
    port: int = LIFX_UDP_PORT,
    max_response_time: float = MAX_RESPONSE_TIME,
    idle_timeout_multiplier: float = IDLE_TIMEOUT_MULTIPLIER,
    device_timeout: float = DEFAULT_REQUEST_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> Device | None
```

Find a specific device by serial number.

| PARAMETER                 | DESCRIPTION                                                                                                 |
| ------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `serial`                  | Serial number as hex string (with or without separators) **TYPE:** `str`                                    |
| `timeout`                 | Discovery timeout in seconds (default DISCOVERY_TIMEOUT) **TYPE:** `float` **DEFAULT:** `DISCOVERY_TIMEOUT` |
| `broadcast_address`       | Broadcast address to use (default "255.255.255.255") **TYPE:** `str` **DEFAULT:** `'255.255.255.255'`       |
| `port`                    | Port to use (default LIFX_UDP_PORT) **TYPE:** `int` **DEFAULT:** `LIFX_UDP_PORT`                            |
| `max_response_time`       | Max time to wait for responses **TYPE:** `float` **DEFAULT:** `MAX_RESPONSE_TIME`                           |
| `idle_timeout_multiplier` | Idle timeout multiplier **TYPE:** `float` **DEFAULT:** `IDLE_TIMEOUT_MULTIPLIER`                            |
| `device_timeout`          | request timeout set on discovered device **TYPE:** `float` **DEFAULT:** `DEFAULT_REQUEST_TIMEOUT`           |
| `max_retries`             | max retries per request set on discovered device **TYPE:** `int` **DEFAULT:** `DEFAULT_MAX_RETRIES`         |

| RETURNS  | DESCRIPTION |
| -------- | ----------- |
| \`Device | None\`      |

Example

```python
# Find by serial number
device = await find_by_serial("d073d5123456")
if device:
    async with device:
        await device.set_power(True)
```

Source code in `src/lifx/api.py`

````python
async def find_by_serial(
    serial: str,
    timeout: float = DISCOVERY_TIMEOUT,
    broadcast_address: str = "255.255.255.255",
    port: int = LIFX_UDP_PORT,
    max_response_time: float = MAX_RESPONSE_TIME,
    idle_timeout_multiplier: float = IDLE_TIMEOUT_MULTIPLIER,
    device_timeout: float = DEFAULT_REQUEST_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> Device | None:
    """Find a specific device by serial number.

    Args:
        serial: Serial number as hex string (with or without separators)
        timeout: Discovery timeout in seconds (default DISCOVERY_TIMEOUT)
        broadcast_address: Broadcast address to use (default "255.255.255.255")
        port: Port to use (default LIFX_UDP_PORT)
        max_response_time: Max time to wait for responses
        idle_timeout_multiplier: Idle timeout multiplier
        device_timeout: request timeout set on discovered device
        max_retries: max retries per request set on discovered device

    Returns:
        Device instance if found, None otherwise

    Example:
        ```python
        # Find by serial number
        device = await find_by_serial("d073d5123456")
        if device:
            async with device:
                await device.set_power(True)
        ```
    """
    # Normalize serial to string format (12-digit hex, no separators)
    serial_str = serial.replace(":", "").replace("-", "").lower()

    async for disc in discover_devices(
        timeout=timeout,
        broadcast_address=broadcast_address,
        port=port,
        max_response_time=max_response_time,
        idle_timeout_multiplier=idle_timeout_multiplier,
        device_timeout=device_timeout,
        max_retries=max_retries,
    ):
        if disc.serial.lower() == serial_str:
            # Detect device type and return appropriate class
            return await disc.create_device()

    return None
````

### find_by_label

```python
find_by_label(
    label: str,
    exact_match: bool = False,
    timeout: float = DISCOVERY_TIMEOUT,
    broadcast_address: str = "255.255.255.255",
    port: int = LIFX_UDP_PORT,
    max_response_time: float = MAX_RESPONSE_TIME,
    idle_timeout_multiplier: float = IDLE_TIMEOUT_MULTIPLIER,
    device_timeout: float = DEFAULT_REQUEST_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> AsyncGenerator[Device]
```

Find LIFX devices by label (name).

Uses a protocol trick by broadcasting GetLabel instead of GetService, which returns all device labels in StateLabel responses. This is more efficient than querying each device individually.

| PARAMETER                 | DESCRIPTION                                                                                                                                                               |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `label`                   | Device label to search for (case-insensitive) **TYPE:** `str`                                                                                                             |
| `exact_match`             | If True, match label exactly and yield at most one device; if False, match substring and yield all matching devices (default False) **TYPE:** `bool` **DEFAULT:** `False` |
| `timeout`                 | Discovery timeout in seconds (default DISCOVERY_TIMEOUT) **TYPE:** `float` **DEFAULT:** `DISCOVERY_TIMEOUT`                                                               |
| `broadcast_address`       | Broadcast address to use (default "255.255.255.255") **TYPE:** `str` **DEFAULT:** `'255.255.255.255'`                                                                     |
| `port`                    | Port to use (default LIFX_UDP_PORT) **TYPE:** `int` **DEFAULT:** `LIFX_UDP_PORT`                                                                                          |
| `max_response_time`       | Max time to wait for responses **TYPE:** `float` **DEFAULT:** `MAX_RESPONSE_TIME`                                                                                         |
| `idle_timeout_multiplier` | Idle timeout multiplier **TYPE:** `float` **DEFAULT:** `IDLE_TIMEOUT_MULTIPLIER`                                                                                          |
| `device_timeout`          | request timeout set on discovered device(s) **TYPE:** `float` **DEFAULT:** `DEFAULT_REQUEST_TIMEOUT`                                                                      |
| `max_retries`             | max retries per request set on discovered device(s) **TYPE:** `int` **DEFAULT:** `DEFAULT_MAX_RETRIES`                                                                    |

| YIELDS                   | DESCRIPTION                 |
| ------------------------ | --------------------------- |
| `AsyncGenerator[Device]` | Matching Device instance(s) |

Example

```python
# Find all devices with "Living" in the label
async for device in find_by_label("Living"):
    async with device:
        await device.set_power(True)

# Find device by exact label match (yields at most one)
async for device in find_by_label("Living Room", exact_match=True):
    async with device:
        await device.set_power(True)
    break  # exact_match yields at most one device
```

Source code in `src/lifx/api.py`

````python
async def find_by_label(
    label: str,
    exact_match: bool = False,
    timeout: float = DISCOVERY_TIMEOUT,
    broadcast_address: str = "255.255.255.255",
    port: int = LIFX_UDP_PORT,
    max_response_time: float = MAX_RESPONSE_TIME,
    idle_timeout_multiplier: float = IDLE_TIMEOUT_MULTIPLIER,
    device_timeout: float = DEFAULT_REQUEST_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> AsyncGenerator[Device]:
    """Find LIFX devices by label (name).

    Uses a protocol trick by broadcasting GetLabel instead of GetService,
    which returns all device labels in StateLabel responses. This is more
    efficient than querying each device individually.

    Args:
        label: Device label to search for (case-insensitive)
        exact_match: If True, match label exactly and yield at most one device;
                     if False, match substring and yield all matching devices
                     (default False)
        timeout: Discovery timeout in seconds (default DISCOVERY_TIMEOUT)
        broadcast_address: Broadcast address to use (default "255.255.255.255")
        port: Port to use (default LIFX_UDP_PORT)
        max_response_time: Max time to wait for responses
        idle_timeout_multiplier: Idle timeout multiplier
        device_timeout: request timeout set on discovered device(s)
        max_retries: max retries per request set on discovered device(s)

    Yields:
        Matching Device instance(s)

    Example:
        ```python
        # Find all devices with "Living" in the label
        async for device in find_by_label("Living"):
            async with device:
                await device.set_power(True)

        # Find device by exact label match (yields at most one)
        async for device in find_by_label("Living Room", exact_match=True):
            async with device:
                await device.set_power(True)
            break  # exact_match yields at most one device
        ```
    """
    async for resp in _discover_with_packet(
        packets.Device.GetLabel(),
        timeout=timeout,
        broadcast_address=broadcast_address,
        port=port,
        max_response_time=max_response_time,
        idle_timeout_multiplier=idle_timeout_multiplier,
    ):
        device_label = resp.response_payload.get("label", "")
        matched = False

        if exact_match:
            # Exact match - return first match only
            if device_label.lower() == label.lower():
                matched = True
        else:
            # Substring match - return all matches
            if label.lower() in device_label.lower():
                matched = True

        if matched:
            # Create DiscoveredDevice from response
            disc = DiscoveredDevice(
                serial=resp.serial,
                ip=resp.ip,
                port=resp.port,
                response_time=resp.response_time,
                timeout=device_timeout,
                max_retries=max_retries,
            )

            device = await disc.create_device()
            if device is not None:
                yield device
````

### find_by_ip

```python
find_by_ip(
    ip: str,
    timeout: float = DISCOVERY_TIMEOUT,
    port: int = LIFX_UDP_PORT,
    max_response_time: float = MAX_RESPONSE_TIME,
    idle_timeout_multiplier: float = IDLE_TIMEOUT_MULTIPLIER,
    device_timeout: float = DEFAULT_REQUEST_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> Device | None
```

Find a LIFX device by IP address.

Uses a targeted discovery by sending the broadcast to the specific IP address, which means only that device will respond (if it exists). This is more efficient than broadcasting to all devices and filtering.

| PARAMETER                 | DESCRIPTION                                                                                                 |
| ------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `ip`                      | Target device IP address **TYPE:** `str`                                                                    |
| `timeout`                 | Discovery timeout in seconds (default DISCOVERY_TIMEOUT) **TYPE:** `float` **DEFAULT:** `DISCOVERY_TIMEOUT` |
| `port`                    | Port to use (default LIFX_UDP_PORT) **TYPE:** `int` **DEFAULT:** `LIFX_UDP_PORT`                            |
| `max_response_time`       | Max time to wait for responses **TYPE:** `float` **DEFAULT:** `MAX_RESPONSE_TIME`                           |
| `idle_timeout_multiplier` | Idle timeout multiplier **TYPE:** `float` **DEFAULT:** `IDLE_TIMEOUT_MULTIPLIER`                            |
| `device_timeout`          | request timeout set on discovered device **TYPE:** `float` **DEFAULT:** `DEFAULT_REQUEST_TIMEOUT`           |
| `max_retries`             | max retries per request set on discovered device **TYPE:** `int` **DEFAULT:** `DEFAULT_MAX_RETRIES`         |

| RETURNS  | DESCRIPTION |
| -------- | ----------- |
| \`Device | None\`      |

Example

```python
# Find device at specific IP
device = await find_by_ip("192.168.1.100")
if device:
    async with device:
        print(f"Found: {device.label}")
```

Source code in `src/lifx/api.py`

````python
async def find_by_ip(
    ip: str,
    timeout: float = DISCOVERY_TIMEOUT,
    port: int = LIFX_UDP_PORT,
    max_response_time: float = MAX_RESPONSE_TIME,
    idle_timeout_multiplier: float = IDLE_TIMEOUT_MULTIPLIER,
    device_timeout: float = DEFAULT_REQUEST_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> Device | None:
    """Find a LIFX device by IP address.

    Uses a targeted discovery by sending the broadcast to the specific IP address,
    which means only that device will respond (if it exists). This is more efficient
    than broadcasting to all devices and filtering.

    Args:
        ip: Target device IP address
        timeout: Discovery timeout in seconds (default DISCOVERY_TIMEOUT)
        port: Port to use (default LIFX_UDP_PORT)
        max_response_time: Max time to wait for responses
        idle_timeout_multiplier: Idle timeout multiplier
        device_timeout: request timeout set on discovered device
        max_retries: max retries per request set on discovered device

    Returns:
        Device instance if found, None otherwise

    Example:
        ```python
        # Find device at specific IP
        device = await find_by_ip("192.168.1.100")
        if device:
            async with device:
                print(f"Found: {device.label}")
        ```
    """
    # Use the target IP as the "broadcast" address - only that device will respond
    async for discovered in discover_devices(
        timeout=timeout,
        broadcast_address=ip,  # Protocol trick: send directly to target IP
        port=port,
        max_response_time=max_response_time,
        idle_timeout_multiplier=idle_timeout_multiplier,
        device_timeout=device_timeout,
        max_retries=max_retries,
    ):
        # Should only get one response (or none)
        return await discovered.create_device()

    return None
````

## Device Group

### DeviceGroup

```python
DeviceGroup(
    devices: Sequence[
        Device | Light | HevLight | InfraredLight | MultiZoneLight | MatrixLight
    ],
)
```

A group of devices for batch operations.

Provides convenient methods to control multiple devices simultaneously.

Example

```python
# Collect devices from discovery
devices = []
async for device in discover():
    devices.append(device)

# Create group and perform batch operations
group = DeviceGroup(devices)
await group.set_power(True)
await group.set_color(Colors.BLUE)
```

| PARAMETER | DESCRIPTION                                           |
| --------- | ----------------------------------------------------- |
| `devices` | List of Device instances **TYPE:** \`Sequence\[Device |

| METHOD                      | DESCRIPTION                                                  |
| --------------------------- | ------------------------------------------------------------ |
| `__aenter__`                | Enter async context manager.                                 |
| `__aexit__`                 | Exit async context manager and close all device connections. |
| `__iter__`                  | Iterate over devices in the group.                           |
| `__len__`                   | Get number of devices in the group.                          |
| `__getitem__`               | Get device by index.                                         |
| `set_power`                 | Set power state for all devices in the group.                |
| `set_color`                 | Set color for all Light devices in the group.                |
| `set_brightness`            | Set brightness for all Light devices in the group.           |
| `pulse`                     | Pulse effect for all Light devices.                          |
| `organize_by_location`      | Organize devices by location label.                          |
| `organize_by_group`         | Organize devices by group label.                             |
| `filter_by_location`        | Filter devices to a specific location.                       |
| `filter_by_group`           | Filter devices to a specific group.                          |
| `get_unassigned_devices`    | Get devices without location or group assigned.              |
| `apply_theme`               | Apply a theme to all devices in the group.                   |
| `invalidate_metadata_cache` | Clear all cached location and group metadata.                |

| ATTRIBUTE          | DESCRIPTION                                                                    |
| ------------------ | ------------------------------------------------------------------------------ |
| `devices`          | Get all the devices in the group. **TYPE:** \`Sequence\[Device                 |
| `lights`           | Get all Light devices in the group. **TYPE:** `list[Light]`                    |
| `hev_lights`       | Get the HEV lights in the group. **TYPE:** `list[HevLight]`                    |
| `infrared_lights`  | Get the Infrared lights in the group. **TYPE:** `list[InfraredLight]`          |
| `multizone_lights` | Get all MultiZone light devices in the group. **TYPE:** `list[MultiZoneLight]` |
| `matrix_lights`    | Get all Matrix light devices in the group. **TYPE:** `list[MatrixLight]`       |

Source code in `src/lifx/api.py`

```python
def __init__(
    self,
    devices: Sequence[
        Device | Light | HevLight | InfraredLight | MultiZoneLight | MatrixLight
    ],
) -> None:
    """Initialize device group.

    Args:
        devices: List of Device instances
    """
    self._devices = devices
    self._lights = [light for light in devices if isinstance(light, Light)]
    self._hev_lights = [light for light in devices if type(light) is HevLight]
    self._infrared_lights = [
        light for light in devices if type(light) is InfraredLight
    ]
    self._multizone_lights = [
        light for light in devices if type(light) is MultiZoneLight
    ]
    self._matrix_lights = [light for light in devices if type(light) is MatrixLight]
    self._locations_cache: dict[str, DeviceGroup] | None = None
    self._groups_cache: dict[str, DeviceGroup] | None = None
    self._location_metadata: dict[str, LocationGrouping] | None = None
    self._group_metadata: dict[str, GroupGrouping] | None = None
```

#### Attributes

##### devices

```python
devices: Sequence[
    Device | HevLight | InfraredLight | Light | MultiZoneLight | MatrixLight
]
```

Get all the devices in the group.

##### lights

```python
lights: list[Light]
```

Get all Light devices in the group.

##### hev_lights

```python
hev_lights: list[HevLight]
```

Get the HEV lights in the group.

##### infrared_lights

```python
infrared_lights: list[InfraredLight]
```

Get the Infrared lights in the group.

##### multizone_lights

```python
multizone_lights: list[MultiZoneLight]
```

Get all MultiZone light devices in the group.

##### matrix_lights

```python
matrix_lights: list[MatrixLight]
```

Get all Matrix light devices in the group.

#### Functions

##### __aenter__

```python
__aenter__() -> DeviceGroup
```

Enter async context manager.

Source code in `src/lifx/api.py`

```python
async def __aenter__(self) -> DeviceGroup:
    """Enter async context manager."""
    return self
```

##### __aexit__

```python
__aexit__(
    exc_type: type[BaseException] | None,
    exc_val: BaseException | None,
    exc_tb: TracebackType | None,
) -> None
```

Exit async context manager and close all device connections.

Source code in `src/lifx/api.py`

```python
async def __aexit__(
    self,
    exc_type: type[BaseException] | None,
    exc_val: BaseException | None,
    exc_tb: TracebackType | None,
) -> None:
    """Exit async context manager and close all device connections."""
    for device in self._devices:
        await device.connection.close()
```

##### __iter__

```python
__iter__() -> Iterator[
    Device | Light | HevLight | InfraredLight | MultiZoneLight | MatrixLight
]
```

Iterate over devices in the group.

Source code in `src/lifx/api.py`

```python
def __iter__(
    self,
) -> Iterator[
    Device | Light | HevLight | InfraredLight | MultiZoneLight | MatrixLight
]:
    """Iterate over devices in the group."""
    return iter(self._devices)
```

##### __len__

```python
__len__() -> int
```

Get number of devices in the group.

Source code in `src/lifx/api.py`

```python
def __len__(self) -> int:
    """Get number of devices in the group."""
    return len(self._devices)
```

##### __getitem__

```python
__getitem__(
    index: int,
) -> Device | Light | HevLight | InfraredLight | MultiZoneLight | MatrixLight
```

Get device by index.

Source code in `src/lifx/api.py`

```python
def __getitem__(
    self, index: int
) -> Device | Light | HevLight | InfraredLight | MultiZoneLight | MatrixLight:
    """Get device by index."""
    return self._devices[index]
```

##### set_power

```python
set_power(on: bool, duration: float = 0.0) -> None
```

Set power state for all devices in the group.

| PARAMETER  | DESCRIPTION                                                                       |
| ---------- | --------------------------------------------------------------------------------- |
| `on`       | True to turn on, False to turn off **TYPE:** `bool`                               |
| `duration` | Transition duration in seconds (default 0.0) **TYPE:** `float` **DEFAULT:** `0.0` |

Example

```python
devices = []
async for device in discover():
    devices.append(device)
group = DeviceGroup(devices)
await group.set_power(True, duration=1.0)
```

Source code in `src/lifx/api.py`

````python
async def set_power(self, on: bool, duration: float = 0.0) -> None:
    """Set power state for all devices in the group.

    Args:
        on: True to turn on, False to turn off
        duration: Transition duration in seconds (default 0.0)

    Example:
        ```python
        devices = []
        async for device in discover():
            devices.append(device)
        group = DeviceGroup(devices)
        await group.set_power(True, duration=1.0)
        ```
    """
    await asyncio.gather(*(light.set_power(on, duration) for light in self.lights))
````

##### set_color

```python
set_color(color: HSBK, duration: float = 0.0) -> None
```

Set color for all Light devices in the group.

| PARAMETER  | DESCRIPTION                                                                       |
| ---------- | --------------------------------------------------------------------------------- |
| `color`    | HSBK color to set **TYPE:** `HSBK`                                                |
| `duration` | Transition duration in seconds (default 0.0) **TYPE:** `float` **DEFAULT:** `0.0` |

Example

```python
devices = []
async for device in discover():
    devices.append(device)
group = DeviceGroup(devices)
await group.set_color(HSBK.from_rgb(255, 0, 0), duration=2.0)
```

Source code in `src/lifx/api.py`

````python
async def set_color(self, color: HSBK, duration: float = 0.0) -> None:
    """Set color for all Light devices in the group.

    Args:
        color: HSBK color to set
        duration: Transition duration in seconds (default 0.0)

    Example:
        ```python
        devices = []
        async for device in discover():
            devices.append(device)
        group = DeviceGroup(devices)
        await group.set_color(HSBK.from_rgb(255, 0, 0), duration=2.0)
        ```
    """
    await asyncio.gather(
        *(light.set_color(color, duration) for light in self.lights)
    )
````

##### set_brightness

```python
set_brightness(brightness: float, duration: float = 0.0) -> None
```

Set brightness for all Light devices in the group.

| PARAMETER    | DESCRIPTION                                                                       |
| ------------ | --------------------------------------------------------------------------------- |
| `brightness` | Brightness level (0.0-1.0) **TYPE:** `float`                                      |
| `duration`   | Transition duration in seconds (default 0.0) **TYPE:** `float` **DEFAULT:** `0.0` |

Example

```python
devices = []
async for device in discover():
    devices.append(device)
group = DeviceGroup(devices)
await group.set_brightness(0.5, duration=1.0)
```

Source code in `src/lifx/api.py`

````python
async def set_brightness(self, brightness: float, duration: float = 0.0) -> None:
    """Set brightness for all Light devices in the group.

    Args:
        brightness: Brightness level (0.0-1.0)
        duration: Transition duration in seconds (default 0.0)

    Example:
        ```python
        devices = []
        async for device in discover():
            devices.append(device)
        group = DeviceGroup(devices)
        await group.set_brightness(0.5, duration=1.0)
        ```
    """
    await asyncio.gather(
        *(light.set_brightness(brightness, duration) for light in self.lights)
    )
````

##### pulse

```python
pulse(color: HSBK, period: float = 1.0, cycles: float = 1.0) -> None
```

Pulse effect for all Light devices.

| PARAMETER | DESCRIPTION                                                         |
| --------- | ------------------------------------------------------------------- |
| `color`   | Color to pulse to **TYPE:** `HSBK`                                  |
| `period`  | Period of one cycle in seconds **TYPE:** `float` **DEFAULT:** `1.0` |
| `cycles`  | Number of cycles **TYPE:** `float` **DEFAULT:** `1.0`               |

Example

```python
devices = []
async for device in discover():
    devices.append(device)
group = DeviceGroup(devices)
await group.pulse(Colors.RED, period=1.0, cycles=1.0)
```

Source code in `src/lifx/api.py`

````python
async def pulse(
    self, color: HSBK, period: float = 1.0, cycles: float = 1.0
) -> None:
    """Pulse effect for all Light devices.

    Args:
        color: Color to pulse to
        period: Period of one cycle in seconds
        cycles: Number of cycles

    Example:
        ```python
        devices = []
        async for device in discover():
            devices.append(device)
        group = DeviceGroup(devices)
        await group.pulse(Colors.RED, period=1.0, cycles=1.0)
        ```
    """
    await asyncio.gather(
        *(light.pulse(color, period, cycles) for light in self.lights)
    )
````

##### organize_by_location

```python
organize_by_location(
    include_unassigned: bool = False,
) -> dict[str, DeviceGroup]
```

Organize devices by location label.

Fetches location metadata if not cached and groups devices by location label.

| PARAMETER            | DESCRIPTION                                                      |
| -------------------- | ---------------------------------------------------------------- |
| `include_unassigned` | Include "Unassigned" group **TYPE:** `bool` **DEFAULT:** `False` |

| RETURNS                  | DESCRIPTION                                                 |
| ------------------------ | ----------------------------------------------------------- |
| `dict[str, DeviceGroup]` | Dictionary mapping location labels to DeviceGroup instances |

Example

```python
devices = []
async for device in discover():
    devices.append(device)
group = DeviceGroup(devices)
by_location = await group.organize_by_location()
kitchen = by_location["Kitchen"]
await kitchen.set_color(Colors.BLUE)
```

Source code in `src/lifx/api.py`

````python
async def organize_by_location(
    self, include_unassigned: bool = False
) -> dict[str, DeviceGroup]:
    """Organize devices by location label.

    Fetches location metadata if not cached and groups devices by location label.

    Args:
        include_unassigned: Include "Unassigned" group

    Returns:
        Dictionary mapping location labels to DeviceGroup instances

    Example:
        ```python
        devices = []
        async for device in discover():
            devices.append(device)
        group = DeviceGroup(devices)
        by_location = await group.organize_by_location()
        kitchen = by_location["Kitchen"]
        await kitchen.set_color(Colors.BLUE)
        ```
    """
    # Fetch metadata if not cached
    if self._location_metadata is None:
        await self._fetch_location_metadata()

    # Build and cache groups
    if self._locations_cache is None:
        self._locations_cache = self._build_location_groups(include_unassigned)

    return self._locations_cache
````

##### organize_by_group

```python
organize_by_group(include_unassigned: bool = False) -> dict[str, DeviceGroup]
```

Organize devices by group label.

Fetches group metadata if not cached and groups devices by group label.

| PARAMETER            | DESCRIPTION                                                      |
| -------------------- | ---------------------------------------------------------------- |
| `include_unassigned` | Include "Unassigned" group **TYPE:** `bool` **DEFAULT:** `False` |

| RETURNS                  | DESCRIPTION                                              |
| ------------------------ | -------------------------------------------------------- |
| `dict[str, DeviceGroup]` | Dictionary mapping group labels to DeviceGroup instances |

Example

```python
devices = []
async for device in discover():
    devices.append(device)
group = DeviceGroup(devices)
by_group = await group.organize_by_group()
bedroom = by_group["Bedroom Lights"]
await bedroom.set_power(False)
```

Source code in `src/lifx/api.py`

````python
async def organize_by_group(
    self, include_unassigned: bool = False
) -> dict[str, DeviceGroup]:
    """Organize devices by group label.

    Fetches group metadata if not cached and groups devices by group label.

    Args:
        include_unassigned: Include "Unassigned" group

    Returns:
        Dictionary mapping group labels to DeviceGroup instances

    Example:
        ```python
        devices = []
        async for device in discover():
            devices.append(device)
        group = DeviceGroup(devices)
        by_group = await group.organize_by_group()
        bedroom = by_group["Bedroom Lights"]
        await bedroom.set_power(False)
        ```
    """
    # Fetch metadata if not cached
    if self._group_metadata is None:
        await self._fetch_group_metadata()

    # Build and cache groups
    if self._groups_cache is None:
        self._groups_cache = self._build_group_groups(include_unassigned)

    return self._groups_cache
````

##### filter_by_location

```python
filter_by_location(label: str, case_sensitive: bool = False) -> DeviceGroup
```

Filter devices to a specific location.

| PARAMETER        | DESCRIPTION                                                                                     |
| ---------------- | ----------------------------------------------------------------------------------------------- |
| `label`          | Location label to filter by **TYPE:** `str`                                                     |
| `case_sensitive` | If True, performs case-sensitive matching (default False) **TYPE:** `bool` **DEFAULT:** `False` |

| RETURNS       | DESCRIPTION                                              |
| ------------- | -------------------------------------------------------- |
| `DeviceGroup` | DeviceGroup containing devices in the specified location |

| RAISES     | DESCRIPTION                 |
| ---------- | --------------------------- |
| `KeyError` | If location label not found |

Example

```python
devices = []
async for device in discover():
    devices.append(device)
group = DeviceGroup(devices)
living_room = await group.filter_by_location("Living Room")
await living_room.set_brightness(0.7)
```

Source code in `src/lifx/api.py`

````python
async def filter_by_location(
    self, label: str, case_sensitive: bool = False
) -> DeviceGroup:
    """Filter devices to a specific location.

    Args:
        label: Location label to filter by
        case_sensitive: If True, performs case-sensitive matching (default False)

    Returns:
        DeviceGroup containing devices in the specified location

    Raises:
        KeyError: If location label not found

    Example:
        ```python
        devices = []
        async for device in discover():
            devices.append(device)
        group = DeviceGroup(devices)
        living_room = await group.filter_by_location("Living Room")
        await living_room.set_brightness(0.7)
        ```
    """
    locations = await self.organize_by_location(include_unassigned=False)

    # Find matching label
    if case_sensitive:
        if label not in locations:
            raise KeyError(f"Location '{label}' not found")
        return locations[label]
    else:
        label_lower = label.lower()
        for loc_label, device_group in locations.items():
            if loc_label.lower() == label_lower:
                return device_group
        raise KeyError(f"Location '{label}' not found")
````

##### filter_by_group

```python
filter_by_group(label: str, case_sensitive: bool = False) -> DeviceGroup
```

Filter devices to a specific group.

| PARAMETER        | DESCRIPTION                                                                                     |
| ---------------- | ----------------------------------------------------------------------------------------------- |
| `label`          | Group label to filter by **TYPE:** `str`                                                        |
| `case_sensitive` | If True, performs case-sensitive matching (default False) **TYPE:** `bool` **DEFAULT:** `False` |

| RETURNS       | DESCRIPTION                                           |
| ------------- | ----------------------------------------------------- |
| `DeviceGroup` | DeviceGroup containing devices in the specified group |

| RAISES     | DESCRIPTION              |
| ---------- | ------------------------ |
| `KeyError` | If group label not found |

Example

```python
devices = []
async for device in discover():
    devices.append(device)
group = DeviceGroup(devices)
bedroom = await group.filter_by_group("Bedroom Lights")
await bedroom.set_color(Colors.WARM_WHITE)
```

Source code in `src/lifx/api.py`

````python
async def filter_by_group(
    self, label: str, case_sensitive: bool = False
) -> DeviceGroup:
    """Filter devices to a specific group.

    Args:
        label: Group label to filter by
        case_sensitive: If True, performs case-sensitive matching (default False)

    Returns:
        DeviceGroup containing devices in the specified group

    Raises:
        KeyError: If group label not found

    Example:
        ```python
        devices = []
        async for device in discover():
            devices.append(device)
        group = DeviceGroup(devices)
        bedroom = await group.filter_by_group("Bedroom Lights")
        await bedroom.set_color(Colors.WARM_WHITE)
        ```
    """
    groups = await self.organize_by_group(include_unassigned=False)

    # Find matching label
    if case_sensitive:
        if label not in groups:
            raise KeyError(f"Group '{label}' not found")
        return groups[label]
    else:
        label_lower = label.lower()
        for grp_label, device_group in groups.items():
            if grp_label.lower() == label_lower:
                return device_group
        raise KeyError(f"Group '{label}' not found")
````

##### get_unassigned_devices

```python
get_unassigned_devices(
    metadata_type: Literal["location", "group"] = "location",
) -> list[Device]
```

Get devices without location or group assigned.

| PARAMETER       | DESCRIPTION                                                                                                          |
| --------------- | -------------------------------------------------------------------------------------------------------------------- |
| `metadata_type` | Type of metadata to check ("location" or "group") **TYPE:** `Literal['location', 'group']` **DEFAULT:** `'location'` |

| RETURNS        | DESCRIPTION                                         |
| -------------- | --------------------------------------------------- |
| `list[Device]` | List of devices without the specified metadata type |

| RAISES         | DESCRIPTION                         |
| -------------- | ----------------------------------- |
| `RuntimeError` | If metadata hasn't been fetched yet |

Example

```python
devices = []
async for device in discover():
    devices.append(device)
group = DeviceGroup(devices)
await group.organize_by_location()
unassigned = group.get_unassigned_devices(metadata_type="location")
print(f"Found {len(unassigned)} devices without location")
```

Source code in `src/lifx/api.py`

````python
def get_unassigned_devices(
    self, metadata_type: Literal["location", "group"] = "location"
) -> list[Device]:
    """Get devices without location or group assigned.

    Args:
        metadata_type: Type of metadata to check ("location" or "group")

    Returns:
        List of devices without the specified metadata type

    Raises:
        RuntimeError: If metadata hasn't been fetched yet

    Example:
        ```python
        devices = []
        async for device in discover():
            devices.append(device)
        group = DeviceGroup(devices)
        await group.organize_by_location()
        unassigned = group.get_unassigned_devices(metadata_type="location")
        print(f"Found {len(unassigned)} devices without location")
        ```
    """
    if metadata_type == "location":
        if self._location_metadata is None:
            raise RuntimeError(
                "Location metadata not fetched. Call organize_by_location() first."
            )
        return [d for d in self._devices if not self._has_location(d)]
    else:
        if self._group_metadata is None:
            raise RuntimeError(
                "Group metadata not fetched. Call organize_by_group() first."
            )
        return [d for d in self._devices if not self._has_group(d)]
````

##### apply_theme

```python
apply_theme(
    theme: Theme, power_on: bool = False, duration: float = 0.0
) -> None
```

Apply a theme to all devices in the group.

Each device applies the theme according to its capabilities:

- Light: Selects random color from theme
- MultiZoneLight: Distributes colors evenly across zones
- MatrixLight: Uses interpolation for smooth gradients
- Other devices: No action (themes only apply to color devices)

| PARAMETER  | DESCRIPTION                                                         |
| ---------- | ------------------------------------------------------------------- |
| `theme`    | Theme to apply **TYPE:** `Theme`                                    |
| `power_on` | Turn on devices if True **TYPE:** `bool` **DEFAULT:** `False`       |
| `duration` | Transition duration in seconds **TYPE:** `float` **DEFAULT:** `0.0` |

Example

```python
from lifx.theme import get_theme

devices = []
async for device in discover():
    devices.append(device)
group = DeviceGroup(devices)
evening = get_theme("evening")
await group.apply_theme(evening, power_on=True, duration=1.0)
```

Source code in `src/lifx/api.py`

````python
async def apply_theme(
    self, theme: Theme, power_on: bool = False, duration: float = 0.0
) -> None:
    """Apply a theme to all devices in the group.

    Each device applies the theme according to its capabilities:
    - Light: Selects random color from theme
    - MultiZoneLight: Distributes colors evenly across zones
    - MatrixLight: Uses interpolation for smooth gradients
    - Other devices: No action (themes only apply to color devices)

    Args:
        theme: Theme to apply
        power_on: Turn on devices if True
        duration: Transition duration in seconds

    Example:
        ```python
        from lifx.theme import get_theme

        devices = []
        async for device in discover():
            devices.append(device)
        group = DeviceGroup(devices)
        evening = get_theme("evening")
        await group.apply_theme(evening, power_on=True, duration=1.0)
        ```
    """
    await asyncio.gather(
        # Apply theme to all lights
        *(light.apply_theme(theme, power_on, duration) for light in self.lights),
        # Apply theme to all multizone lights
        *(
            multizone.apply_theme(theme, power_on, duration)
            for multizone in self.multizone_lights
        ),
        # Apply theme to all matrix light devices
        *(
            matrix.apply_theme(theme, power_on, duration)
            for matrix in self.matrix_lights
        ),
    )
````

##### invalidate_metadata_cache

```python
invalidate_metadata_cache() -> None
```

Clear all cached location and group metadata.

Use this if you've changed device locations/groups and want to re-fetch.

Example

```python
devices = []
async for device in discover():
    devices.append(device)
group = DeviceGroup(devices)

# First organization
by_location = await group.organize_by_location()

# ... change device locations ...

# Clear cache and re-organize
group.invalidate_metadata_cache()
by_location = await group.organize_by_location()
```

Source code in `src/lifx/api.py`

````python
def invalidate_metadata_cache(self) -> None:
    """Clear all cached location and group metadata.

    Use this if you've changed device locations/groups and want to re-fetch.

    Example:
        ```python
        devices = []
        async for device in discover():
            devices.append(device)
        group = DeviceGroup(devices)

        # First organization
        by_location = await group.organize_by_location()

        # ... change device locations ...

        # Clear cache and re-organize
        group.invalidate_metadata_cache()
        by_location = await group.organize_by_location()
        ```
    """
    self._locations_cache = None
    self._groups_cache = None
    self._location_metadata = None
    self._group_metadata = None
````

## Organizational Groupings

Dataclasses for organizing devices by location or group. Returned by `DeviceGroup.organize_by_location()` and `DeviceGroup.organize_by_group()`.

### LocationGrouping

Location-based device grouping returned by `DeviceGroup.organize_by_location()`.

#### LocationGrouping

```python
LocationGrouping(uuid: str, label: str, devices: list[Device], updated_at: int)
```

Organizational structure for location-based grouping.

| METHOD            | DESCRIPTION                                  |
| ----------------- | -------------------------------------------- |
| `to_device_group` | Convert to DeviceGroup for batch operations. |

##### Functions

###### to_device_group

```python
to_device_group() -> DeviceGroup
```

Convert to DeviceGroup for batch operations.

Source code in `src/lifx/api.py`

```python
def to_device_group(self) -> DeviceGroup:
    """Convert to DeviceGroup for batch operations."""
    return DeviceGroup(self.devices)
```

### GroupGrouping

Group-based device grouping returned by `DeviceGroup.organize_by_group()`.

#### GroupGrouping

```python
GroupGrouping(uuid: str, label: str, devices: list[Device], updated_at: int)
```

Organizational structure for group-based grouping.

| METHOD            | DESCRIPTION                                  |
| ----------------- | -------------------------------------------- |
| `to_device_group` | Convert to DeviceGroup for batch operations. |

##### Functions

###### to_device_group

```python
to_device_group() -> DeviceGroup
```

Convert to DeviceGroup for batch operations.

Source code in `src/lifx/api.py`

```python
def to_device_group(self) -> DeviceGroup:
    """Convert to DeviceGroup for batch operations."""
    return DeviceGroup(self.devices)
```

## Examples

### Simple Discovery

```python
from lifx import discover, DeviceGroup, Colors


async def main():
    count: int = 0
    async for device in discover():
        count += 1
        await device.set_power(True)
        await device.set_color(Colors.BLUE)

    print(f"Found {count} devices")
```

### Find by Serial Number

```python
from lifx import find_by_serial


async def main():
    # Find specific device by serial number
    device = await find_by_serial("d073d5123456")
    if device:
        async with device:
            await device.set_power(True)
```

### Find by Label

```python
from lifx import find_by_label, Colors


async def main():
    # Find all devices with "Living" in the label (substring match)
    async for device in find_by_label("Living"):  # May match "Living Room", "Living Area", etc.

        await device.set_power(True)

    # Find device with exact label match
    async for device in find_by_label("Living Room", exact_match=True):
        await device.set_color(Colors.WARM_WHITE)
        break  # exact_match returns at most one device
```

### Find by IP Address

```python
from lifx import find_by_ip


async def main():
    # Find device at specific IP address
    device = await find_by_ip("192.168.1.100")
    if device:
        async with device:
            await device.set_power(True)
```
