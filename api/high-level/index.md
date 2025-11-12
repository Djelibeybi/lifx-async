# High-Level API

The high-level API provides simplified functions for common LIFX operations. These are the recommended entry points for most users.

## Discovery Functions

### discover

```python
discover(
    timeout: float = 3.0,
    broadcast_address: str = "255.255.255.255",
    port: int = LIFX_UDP_PORT,
    max_response_time: float = MAX_RESPONSE_TIME,
    idle_timeout_multiplier: float = IDLE_TIMEOUT_MULTIPLIER,
) -> DiscoveryContext
```

Discover LIFX devices and return a discovery context manager.

This function returns an async context manager that performs device discovery and automatically handles connection/disconnection.

| PARAMETER                 | DESCRIPTION                                                                                           |
| ------------------------- | ----------------------------------------------------------------------------------------------------- |
| `timeout`                 | Discovery timeout in seconds (default 3.0) **TYPE:** `float` **DEFAULT:** `3.0`                       |
| `broadcast_address`       | Broadcast address to use (default "255.255.255.255") **TYPE:** `str` **DEFAULT:** `'255.255.255.255'` |
| `port`                    | Port to use (default LIFX_UDP_PORT) **TYPE:** `int` **DEFAULT:** `LIFX_UDP_PORT`                      |
| `max_response_time`       | Max time to wait for responses **TYPE:** `float` **DEFAULT:** `MAX_RESPONSE_TIME`                     |
| `idle_timeout_multiplier` | Idle timeout multiplier **TYPE:** `float` **DEFAULT:** `IDLE_TIMEOUT_MULTIPLIER`                      |

| RETURNS            | DESCRIPTION                            |
| ------------------ | -------------------------------------- |
| `DiscoveryContext` | DiscoveryContext async context manager |

Example

```python
# Discover and control all devices using context manager
async with discover() as group:
    await group.set_power(True)
    await group.set_color(Colors.BLUE)
```

Source code in `src/lifx/api.py`

````python
def discover(
    timeout: float = 3.0,
    broadcast_address: str = "255.255.255.255",
    port: int = LIFX_UDP_PORT,
    max_response_time: float = MAX_RESPONSE_TIME,
    idle_timeout_multiplier: float = IDLE_TIMEOUT_MULTIPLIER,
) -> DiscoveryContext:
    """Discover LIFX devices and return a discovery context manager.

    This function returns an async context manager that performs device
    discovery and automatically handles connection/disconnection.

    Args:
        timeout: Discovery timeout in seconds (default 3.0)
        broadcast_address: Broadcast address to use (default "255.255.255.255")
        port: Port to use (default LIFX_UDP_PORT)
        max_response_time: Max time to wait for responses
        idle_timeout_multiplier: Idle timeout multiplier

    Returns:
        DiscoveryContext async context manager

    Example:
        ```python
        # Discover and control all devices using context manager
        async with discover() as group:
            await group.set_power(True)
            await group.set_color(Colors.BLUE)
        ```
    """
    return DiscoveryContext(
        timeout=timeout,
        broadcast_address=broadcast_address,
        port=port,
        max_response_time=max_response_time,
        idle_timeout_multiplier=idle_timeout_multiplier,
    )
````

### find_lights

```python
find_lights(
    label_contains: str | None = None,
    timeout: float = 3.0,
    broadcast_address: str = "255.255.255.255",
    port: int = LIFX_UDP_PORT,
    max_response_time: float = MAX_RESPONSE_TIME,
    idle_timeout_multiplier: float = IDLE_TIMEOUT_MULTIPLIER,
) -> list[Light]
```

Find Light devices with optional label filtering.

| PARAMETER                 | DESCRIPTION                                                                                           |
| ------------------------- | ----------------------------------------------------------------------------------------------------- |
| `label_contains`          | Filter by label substring (case-insensitive) **TYPE:** \`str                                          |
| `timeout`                 | Discovery timeout in seconds (default 3.0) **TYPE:** `float` **DEFAULT:** `3.0`                       |
| `broadcast_address`       | Broadcast address to use (default "255.255.255.255") **TYPE:** `str` **DEFAULT:** `'255.255.255.255'` |
| `port`                    | Port to use (default LIFX_UDP_PORT) **TYPE:** `int` **DEFAULT:** `LIFX_UDP_PORT`                      |
| `max_response_time`       | Max time to wait for responses **TYPE:** `float` **DEFAULT:** `MAX_RESPONSE_TIME`                     |
| `idle_timeout_multiplier` | Idle timeout multiplier **TYPE:** `float` **DEFAULT:** `IDLE_TIMEOUT_MULTIPLIER`                      |

| RETURNS       | DESCRIPTION                                   |
| ------------- | --------------------------------------------- |
| `list[Light]` | List of Light instances matching the criteria |

Example

```python
# Find all lights with "bedroom" in the label
lights = await find_lights(label_contains="bedroom")
for light in lights:
    async with light:
        await light.set_color(Colors.WARM_WHITE)
```

Source code in `src/lifx/api.py`

````python
async def find_lights(
    label_contains: str | None = None,
    timeout: float = 3.0,
    broadcast_address: str = "255.255.255.255",
    port: int = LIFX_UDP_PORT,
    max_response_time: float = MAX_RESPONSE_TIME,
    idle_timeout_multiplier: float = IDLE_TIMEOUT_MULTIPLIER,
) -> list[Light]:
    """Find Light devices with optional label filtering.

    Args:
        label_contains: Filter by label substring (case-insensitive)
        timeout: Discovery timeout in seconds (default 3.0)
        broadcast_address: Broadcast address to use (default "255.255.255.255")
        port: Port to use (default LIFX_UDP_PORT)
        max_response_time: Max time to wait for responses
        idle_timeout_multiplier: Idle timeout multiplier

    Returns:
        List of Light instances matching the criteria

    Example:
        ```python
        # Find all lights with "bedroom" in the label
        lights = await find_lights(label_contains="bedroom")
        for light in lights:
            async with light:
                await light.set_color(Colors.WARM_WHITE)
        ```
    """
    discovered = await discover_devices(
        timeout=timeout,
        broadcast_address=broadcast_address,
        port=port,
        max_response_time=max_response_time,
        idle_timeout_multiplier=idle_timeout_multiplier,
    )

    # Detect device types in parallel
    results: list[Device | None] = [None] * len(discovered)

    async def detect_and_store(index: int, disc: DiscoveredDevice) -> None:
        results[index] = await _detect_device_type(disc)

    async with asyncio.TaskGroup() as tg:
        for i, disc in enumerate(discovered):
            tg.create_task(detect_and_store(i, disc))

    devices = [d for d in results if d is not None]

    # Filter to only Light devices (and subclasses like MultiZoneLight, TileDevice)
    lights: list[Light] = [d for d in devices if isinstance(d, Light)]

    # If label filtering is requested, connect and check label
    if label_contains is not None:
        filtered_lights: list[Light] = []
        for light in lights:
            async with light:
                try:
                    label = await light.get_label()
                    if label_contains.lower() in label.lower():
                        filtered_lights.append(light)
                except LifxTimeoutError:
                    # Skip devices that fail to respond
                    _LOGGER.warning(
                        {
                            "class": "find_lights",
                            "method": "filter_devices",
                            "action": "no_response",
                            "serial": light.serial,
                            "ip": light.ip,
                        }
                    )
        return filtered_lights

    return lights
````

### find_by_serial

```python
find_by_serial(
    serial: bytes | str,
    timeout: float = 3.0,
    broadcast_address: str = "255.255.255.255",
    port: int = LIFX_UDP_PORT,
    max_response_time: float = MAX_RESPONSE_TIME,
    idle_timeout_multiplier: float = IDLE_TIMEOUT_MULTIPLIER,
) -> Device | None
```

Find a specific device by serial number.

| PARAMETER                 | DESCRIPTION                                                                                           |
| ------------------------- | ----------------------------------------------------------------------------------------------------- |
| `serial`                  | Serial number as bytes or hex string (with or without separators) **TYPE:** \`bytes                   |
| `timeout`                 | Discovery timeout in seconds (default 3.0) **TYPE:** `float` **DEFAULT:** `3.0`                       |
| `broadcast_address`       | Broadcast address to use (default "255.255.255.255") **TYPE:** `str` **DEFAULT:** `'255.255.255.255'` |
| `port`                    | Port to use (default LIFX_UDP_PORT) **TYPE:** `int` **DEFAULT:** `LIFX_UDP_PORT`                      |
| `max_response_time`       | Max time to wait for responses **TYPE:** `float` **DEFAULT:** `MAX_RESPONSE_TIME`                     |
| `idle_timeout_multiplier` | Idle timeout multiplier **TYPE:** `float` **DEFAULT:** `IDLE_TIMEOUT_MULTIPLIER`                      |

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
    serial: bytes | str,
    timeout: float = 3.0,
    broadcast_address: str = "255.255.255.255",
    port: int = LIFX_UDP_PORT,
    max_response_time: float = MAX_RESPONSE_TIME,
    idle_timeout_multiplier: float = IDLE_TIMEOUT_MULTIPLIER,
) -> Device | None:
    """Find a specific device by serial number.

    Args:
        serial: Serial number as bytes or hex string (with or without separators)
        timeout: Discovery timeout in seconds (default 3.0)
        broadcast_address: Broadcast address to use (default "255.255.255.255")
        port: Port to use (default LIFX_UDP_PORT)
        max_response_time: Max time to wait for responses
        idle_timeout_multiplier: Idle timeout multiplier

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
    if isinstance(serial, bytes):
        serial_str = serial.hex()
    else:
        serial_str = serial.replace(":", "").replace("-", "").lower()

    discovered = await discover_devices(
        timeout=timeout,
        broadcast_address=broadcast_address,
        port=port,
        max_response_time=max_response_time,
        idle_timeout_multiplier=idle_timeout_multiplier,
    )

    for d in discovered:
        if d.serial.lower() == serial_str:
            # Detect device type and return appropriate class
            return await _detect_device_type(d)

    return None
````

## Discovery Context

### DiscoveryContext

```python
DiscoveryContext(
    timeout: float,
    broadcast_address: str,
    port: int,
    max_response_time: float = MAX_RESPONSE_TIME,
    idle_timeout_multiplier: float = IDLE_TIMEOUT_MULTIPLIER,
)
```

Async context manager for device discovery.

Handles device discovery and automatic connection/disconnection. Use with the `discover()` function for convenient device discovery.

Example

```python
async with discover(timeout=5.0) as group:
    await group.set_power(True)
```

| PARAMETER                 | DESCRIPTION                                                                       |
| ------------------------- | --------------------------------------------------------------------------------- |
| `timeout`                 | Discovery timeout in seconds **TYPE:** `float`                                    |
| `broadcast_address`       | Broadcast address to use **TYPE:** `str`                                          |
| `port`                    | Port to use **TYPE:** `int`                                                       |
| `max_response_time`       | Max time to wait for responses **TYPE:** `float` **DEFAULT:** `MAX_RESPONSE_TIME` |
| `idle_timeout_multiplier` | Idle timeout multiplier **TYPE:** `float` **DEFAULT:** `IDLE_TIMEOUT_MULTIPLIER`  |

| METHOD       | DESCRIPTION                           |
| ------------ | ------------------------------------- |
| `__aenter__` | Discover devices and connect to them. |
| `__aexit__`  | Disconnect from all devices.          |

Source code in `src/lifx/api.py`

```python
def __init__(
    self,
    timeout: float,
    broadcast_address: str,
    port: int,
    max_response_time: float = MAX_RESPONSE_TIME,
    idle_timeout_multiplier: float = IDLE_TIMEOUT_MULTIPLIER,
) -> None:
    """Initialize discovery context.

    Args:
        timeout: Discovery timeout in seconds
        broadcast_address: Broadcast address to use
        port: Port to use
        max_response_time: Max time to wait for responses
        idle_timeout_multiplier: Idle timeout multiplier
    """
    self.timeout = timeout
    self.broadcast_address = broadcast_address
    self.port = port
    self._group: DeviceGroup | None = None
    self._max_response_time = max_response_time
    self._idle_timeout_multiplier = idle_timeout_multiplier
```

#### Functions

##### __aenter__

```python
__aenter__() -> DeviceGroup
```

Discover devices and connect to them.

| RETURNS       | DESCRIPTION                                   |
| ------------- | --------------------------------------------- |
| `DeviceGroup` | DeviceGroup containing all discovered devices |

Source code in `src/lifx/api.py`

```python
async def __aenter__(self) -> DeviceGroup:
    """Discover devices and connect to them.

    Returns:
        DeviceGroup containing all discovered devices
    """
    # Perform discovery
    discovered = await discover_devices(
        timeout=self.timeout,
        broadcast_address=self.broadcast_address,
        port=self.port,
        max_response_time=self._max_response_time,
        idle_timeout_multiplier=self._idle_timeout_multiplier,
    )

    # Detect device types and instantiate appropriate classes
    results: list[Device | None] = [None] * len(discovered)

    async def detect_and_store(index: int, disc: DiscoveredDevice) -> None:
        results[index] = await _detect_device_type(disc)

    async with asyncio.TaskGroup() as tg:
        for i, disc in enumerate(discovered):
            tg.create_task(detect_and_store(i, disc))

    # Filter out None values (unresponsive devices)
    devices = [d for d in results if d is not None]

    # Create group and connect all devices
    self._group = DeviceGroup(devices)
    await self._group.__aenter__()

    return self._group
```

##### __aexit__

```python
__aexit__(
    exc_type: type[BaseException] | None,
    exc_val: BaseException | None,
    exc_tb: TracebackType | None,
) -> None
```

Disconnect from all devices.

Source code in `src/lifx/api.py`

```python
async def __aexit__(
    self,
    exc_type: type[BaseException] | None,
    exc_val: BaseException | None,
    exc_tb: TracebackType | None,
) -> None:
    """Disconnect from all devices."""
    if self._group:
        await self._group.__aexit__(exc_type, exc_val, exc_tb)
```

## Device Group

### DeviceGroup

```python
DeviceGroup(
    devices: list[
        Device | Light | HevLight | InfraredLight | MultiZoneLight | TileDevice
    ],
)
```

A group of devices for batch operations.

Provides convenient methods to control multiple devices simultaneously.

Example

```python
async with discover() as group:
    await group.set_power(True)
    await group.set_color(Colors.BLUE)
```

| PARAMETER | DESCRIPTION                                       |
| --------- | ------------------------------------------------- |
| `devices` | List of Device instances **TYPE:** \`list\[Device |

| METHOD                      | DESCRIPTION                                        |
| --------------------------- | -------------------------------------------------- |
| `__aenter__`                | Enter async context manager.                       |
| `__aexit__`                 | Exit async context manager.                        |
| `__iter__`                  | Iterate over devices in the group.                 |
| `__len__`                   | Get number of devices in the group.                |
| `set_power`                 | Set power state for all devices in the group.      |
| `set_color`                 | Set color for all Light devices in the group.      |
| `set_brightness`            | Set brightness for all Light devices in the group. |
| `pulse`                     | Pulse effect for all Light devices.                |
| `organize_by_location`      | Organize devices by location label.                |
| `organize_by_group`         | Organize devices by group label.                   |
| `filter_by_location`        | Filter devices to a specific location.             |
| `filter_by_group`           | Filter devices to a specific group.                |
| `get_unassigned_devices`    | Get devices without location or group assigned.    |
| `apply_theme`               | Apply a theme to all devices in the group.         |
| `invalidate_metadata_cache` | Clear all cached location and group metadata.      |

| ATTRIBUTE          | DESCRIPTION                                                                    |
| ------------------ | ------------------------------------------------------------------------------ |
| `devices`          | Get all the devices in the group. **TYPE:** `list[Device]`                     |
| `lights`           | Get all Light devices in the group. **TYPE:** `list[Light]`                    |
| `hev_lights`       | Get the HEV lights in the group. **TYPE:** `list[HevLight]`                    |
| `infrared_lights`  | Get the Infrared lights in the group. **TYPE:** `list[InfraredLight]`          |
| `multizone_lights` | Get all MultiZone light devices in the group. **TYPE:** `list[MultiZoneLight]` |
| `tiles`            | Get all Tile devices in the group. **TYPE:** `list[TileDevice]`                |

Source code in `src/lifx/api.py`

```python
def __init__(
    self,
    devices: list[
        Device | Light | HevLight | InfraredLight | MultiZoneLight | TileDevice
    ],
) -> None:
    """Initialize device group.

    Args:
        devices: List of Device instances
    """
    self._devices = devices
    self._locations_cache: dict[str, DeviceGroup] | None = None
    self._groups_cache: dict[str, DeviceGroup] | None = None
    self._location_metadata: dict[bytes, LocationGrouping] | None = None
    self._group_metadata: dict[bytes, GroupGrouping] | None = None
```

#### Attributes

##### devices

```python
devices: list[Device]
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

##### tiles

```python
tiles: list[TileDevice]
```

Get all Tile devices in the group.

#### Functions

##### __aenter__

```python
__aenter__() -> DeviceGroup
```

Enter async context manager.

Note: With the new connection architecture, explicit connect/disconnect is not needed. Connections are managed automatically by the connection pool when requests are made.

Source code in `src/lifx/api.py`

```python
async def __aenter__(self) -> DeviceGroup:
    """Enter async context manager.

    Note: With the new connection architecture, explicit connect/disconnect
    is not needed. Connections are managed automatically by the connection
    pool when requests are made.
    """
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

Exit async context manager.

Note: Cleanup is handled automatically by the connection pool.

Source code in `src/lifx/api.py`

```python
async def __aexit__(
    self,
    exc_type: type[BaseException] | None,
    exc_val: BaseException | None,
    exc_tb: TracebackType | None,
) -> None:
    """Exit async context manager.

    Note: Cleanup is handled automatically by the connection pool.
    """
    pass
```

##### __iter__

```python
__iter__() -> Iterator[
    Device | Light | HevLight | InfraredLight | MultiZoneLight | TileDevice
]
```

Iterate over devices in the group.

Source code in `src/lifx/api.py`

```python
def __iter__(
    self,
) -> Iterator[
    Device | Light | HevLight | InfraredLight | MultiZoneLight | TileDevice
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
async with discover() as group:
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
        async with discover() as group:
            await group.set_power(True, duration=1.0)
        ```
    """
    async with asyncio.TaskGroup() as tg:
        for light in self.lights:
            tg.create_task(light.set_power(on, duration))
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
async with discover() as group:
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
        async with discover() as group:
            await group.set_color(HSBK.from_rgb(255, 0, 0), duration=2.0)
        ```
    """
    async with asyncio.TaskGroup() as tg:
        for light in self.lights:
            tg.create_task(light.set_color(color, duration))
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
async with discover() as group:
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
        async with discover() as group:
            await group.set_brightness(0.5, duration=1.0)
        ```
    """
    async with asyncio.TaskGroup() as tg:
        for light in self.lights:
            tg.create_task(light.set_brightness(brightness, duration))
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
async with discover() as group:
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
        async with discover() as group:
            await group.pulse(Colors.RED, period=1.0, cycles=1.0)
        ```
    """
    async with asyncio.TaskGroup() as tg:
        for light in self.lights:
            tg.create_task(light.pulse(color, period, cycles))
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
async with discover() as group:
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
        async with discover() as group:
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
async with discover() as group:
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
        async with discover() as group:
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
async with discover() as group:
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
        async with discover() as group:
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
async with discover() as group:
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
        async with discover() as group:
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
async with discover() as group:
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
        async with discover() as group:
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
- TileDevice: Uses interpolation for smooth gradients
- Other devices: No action (themes only apply to color devices)

| PARAMETER  | DESCRIPTION                                                         |
| ---------- | ------------------------------------------------------------------- |
| `theme`    | Theme to apply **TYPE:** `Theme`                                    |
| `power_on` | Turn on devices if True **TYPE:** `bool` **DEFAULT:** `False`       |
| `duration` | Transition duration in seconds **TYPE:** `float` **DEFAULT:** `0.0` |

Example

```python
from lifx.theme import get_theme

async with discover() as group:
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
    - TileDevice: Uses interpolation for smooth gradients
    - Other devices: No action (themes only apply to color devices)

    Args:
        theme: Theme to apply
        power_on: Turn on devices if True
        duration: Transition duration in seconds

    Example:
        ```python
        from lifx.theme import get_theme

        async with discover() as group:
            evening = get_theme("evening")
            await group.apply_theme(evening, power_on=True, duration=1.0)
        ```
    """
    async with asyncio.TaskGroup() as tg:
        # Apply theme to all lights
        for light in self.lights:
            tg.create_task(light.apply_theme(theme, power_on, duration))

        # Apply theme to all multizone lights
        for multizone in self.multizone_lights:
            tg.create_task(multizone.apply_theme(theme, power_on, duration))

        # Apply theme to all tile devices
        for tile in self.tiles:
            tg.create_task(tile.apply_theme(theme, power_on, duration))
````

##### invalidate_metadata_cache

```python
invalidate_metadata_cache() -> None
```

Clear all cached location and group metadata.

Use this if you've changed device locations/groups and want to re-fetch.

Example

```python
async with discover() as group:
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
        async with discover() as group:
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

## Examples

### Simple Discovery

```python
from lifx import discover, Colors


async def main():
    async with discover() as group:
        print(f"Found {len(group.devices)} devices")
        await group.set_power(True)
        await group.set_color(Colors.BLUE)
```

### Find Specific Lights

```python
from lifx import find_lights


async def main():
    # Find all lights with "Kitchen" in the label
    async with find_lights(label_filter="Kitchen") as lights:
        for light in lights:
            await light.set_brightness(0.8)
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
