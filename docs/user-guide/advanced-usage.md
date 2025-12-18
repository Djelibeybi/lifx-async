# Advanced Usage

This guide covers advanced lifx patterns and techniques for building robust LIFX integrations.

## Table of Contents

- [Discovery Methods](#discovery-methods)
- [Storing State](#storing-state)
- [Connection Management](#connection-management)
- [Concurrency Patterns](#concurrency-patterns)
- [Error Handling](#error-handling)
- [Device Capabilities](#device-capabilities)
- [Custom Effects](#custom-effects)
- [Performance Optimization](#performance-optimization)

## Discovery Methods

lifx-async provides two discovery methods with different trade-offs:

### UDP Broadcast Discovery

The traditional discovery method broadcasts to all devices on the network:

```python
from lifx import discover

async def broadcast_discovery():
    async for device in discover(timeout=5.0):
        async with device:
            color, power, label = await device.get_color()
            print(f"Found: {label} ({type(device).__name__})")
```

**Characteristics:**

- Sends 1 broadcast + N queries (one per device for type detection)
- Works on any local network
- May miss devices on other subnets

### mDNS Discovery

mDNS discovery uses DNS-SD to find devices with a single multicast query:

```python
from lifx import discover_mdns

async def mdns_discovery():
    async for device in discover_mdns(timeout=5.0):
        async with device:
            color, power, label = await device.get_color()
            print(f"Found: {label} ({type(device).__name__})")
```

**Characteristics:**

- Single network query (device type in TXT record)
- Faster discovery with immediate type detection
- Can work across subnets with an mDNS reflector
- Zero dependencies (uses Python stdlib only)

### Low-Level mDNS API

For raw mDNS data without device instantiation:

```python
from lifx import discover_lifx_services

async def raw_mdns_discovery():
    async for record in discover_lifx_services(timeout=5.0):
        print(f"Serial: {record.serial}")
        print(f"IP: {record.ip}:{record.port}")
        print(f"Product ID: {record.product_id}")
        print(f"Firmware: {record.firmware}")
```

### Choosing a Discovery Method

| Scenario | Recommended Method |
|----------|-------------------|
| General use | `discover()` or `discover_mdns()` |
| Fastest discovery | `discover_mdns()` |
| Cross-subnet (with reflector) | `discover_mdns()` |
| Maximum compatibility | `discover()` |
| Raw device data | `discover_lifx_services()` |

## Storing State

Device properties return cached values that were last retrieved from the device.

lifx-async automatically populates initial state values when a device is used as an async context manager.

### Understanding Stored State

All device state properties return cached values or `None` if not yet fetched:

```python
from lifx import Light

async def check_stored_state():
    async with await Light.from_ip("192.168.1.100") as light:
        # Property returns cached value or None
        label = light.label
        if label:
            print(f"Cached label: {label}")
        else:
            print("No cached label - fetching from device")
            label = await light.get_label()
            print(f"Label: {label}")
```

### Fetching Fresh Data

Use the `get_*()` methods to always fetch from the device:

```python
async def always_fresh():
    async with await Light.from_ip("192.168.1.100") as light:
        # Always fetches from device
        # Note: get_color() returns a tuple of (color, power, label)
        color, power, label = await light.get_color()

        # Get other device info
        version = await light.get_version()

        # Some properties cache semi-static data
        cached_label = light.label  # Updated from get_color()
```

### Working with Cached Data

Use cached values when available for semi-static data, always fetch volatile state:

```python
async def use_cached_or_fetch():
    async with await Light.from_ip("192.168.1.100") as light:
        # Check if we have cached label (semi-static)
        label = light.label
        if label:
            print(f"Using cached label: {label}")
        else:
            print("No cached label, fetching from device")
            label = await light.get_label()
            print(f"Fetched label: {label}")

        # For volatile state (power, color), always fetch fresh data
        # get_color() will only cache the label
        color, power, label = await light.get_color()
        print(f"Current state of {light.label} - Power: {power}, Color: {color}")
```

### Available Properties

#### Device Properties

- `Device.label` - Device name/label
- `Device.version` - Vendor ID and Product ID
- `Device.host_firmware` - Major and minor host firmware version and build number
- `Device.wifi_firmware` - Major and minor wifi firmware version and build number
- `Device.location` - Device location name/label
- `Device.group` - Device group name/label

##### Non-State Properties

- `Device.model` - Device product model

#### Light properties

##### Non-State Properties

- `Light.min_kelvin` - Lowest supported kelvin value
- `Light.max_kelvin` - Highest supported kelvin value

#### InfraredLight properties

- `InfraredLight.infrared` - Infrared brightness

#### HevLight properties:

- `HevLight.hev_config` - HEV configuration
- `HevLight.hev_result` - Last HEV result

#### MultiZoneLight properties:

- `MultiZoneLight.zone_count` - Number of zones
- `MultiZoneLight.multizone_effect` - Either MOVE or OFF

#### MatrixLight properties:

- `MatrixLight.tile_count` - Number of tiles on the chain
- `MatrixLight.device_chain` - Details of each tile on the chain
- `MatrixLight.tile_effect` - Either MORPH, FLAME, SKY or OFF

#### CeilingLight properties:

- `CeilingLight.uplight_zone` - Zone index of the uplight component
- `CeilingLight.downlight_zones` - Slice representing downlight zones
- `CeilingLight.uplight_is_on` - True if uplight has brightness > 0 (requires recent data)
- `CeilingLight.downlight_is_on` - True if any downlight zone has brightness > 0 (requires recent data)

**Note**: Volatile state properties (power, color, hev_cycle, zones, tile_colors) have been removed. Always use `get_*()` methods to fetch these values from devices as they change too frequently to benefit from caching.

All cached properties return `None` if no data has been cached yet, or the cached value if available.


## Connection Management

### Understanding Lazy Connections

Each device owns its own connection that opens lazily on first request:

```python
from lifx import Light

async def main():
    async with await Light.from_ip("192.168.1.100") as light:
        # Connection opens automatically on first request
        await light.set_power(True)
        # All subsequent operations reuse the same connection
        await light.set_color(Colors.BLUE)
        await light.get_label()
        # Connection automatically closed when exiting context
```

**Benefits:**

- Simple lifecycle: one connection per device
- Lazy opening: connection opens only when needed
- Automatic cleanup on context exit
- Requests are serialized to prevent response mixing

## Concurrency Patterns

### Concurrent Requests (Single Device)

Send multiple requests concurrently to one device:

```python
import asyncio
from lifx import Light

async def concurrent_operations():
    async with await Light.from_ip("192.168.1.100") as light:
        # These execute concurrently!
        # get_color() returns (color, power, label)
        (color, power, label), version = await asyncio.gather(
            light.get_color(),
            light.get_version(),
        )

        print(f"{label}: Power={power}, Color={color}, Firmware={version.firmware}")
```

**Performance Note:** Concurrent requests execute with maximum parallelism. However, per the LIFX protocol specification, devices can handle approximately 20 messages per second. When sending many concurrent requests to a single device, consider implementing rate limiting in your application to avoid overwhelming the device.

### Multi-Device Control

Control multiple devices in parallel:

```python
import asyncio
from lifx import discover, DeviceGroup, Colors

async def multi_device_control():
    devices = []
    async for device in discover():
        devices.append(device)
    group = DeviceGroup(devices)

    # Create different tasks for different devices
    tasks = [
        group.devices[0].set_color(Colors.RED),
        group.devices[1].set_color(Colors.GREEN),
        group.devices[2].set_color(Colors.BLUE),
    ]

    # Execute all at once
    await asyncio.gather(*tasks)
```

### Batched Discovery

Discover devices in batches for large networks:

```python
from lifx.network.discovery import discover_devices

async def discover_in_batches():
    # First batch: quick discovery
    devices_quick = await discover_devices(
        timeout=1.0,
        broadcast_address="255.255.255.255"
    )

    # Second batch: thorough discovery
    if len(devices_quick) < expected_count:
        devices_full = await discover_devices(
            timeout=5.0,
            broadcast_address="255.255.255.255"
        )
        return devices_full

    return devices_quick
```

## Error Handling

### Exception Hierarchy

```python
from lifx import (
    LifxError,              # Base exception
    LifxTimeoutError,       # Request timeout
    LifxConnectionError,    # Connection failed
    LifxProtocolError,      # Invalid protocol response
    LifxDeviceNotFoundError,# Device not discovered
    LifxNetworkError,       # Network issues
    LifxUnsupportedCommandError,  # Device doesn't support operation
)
```

### Robust Error Handling

```python
import asyncio
from lifx import Light, Colors, LifxTimeoutError, LifxConnectionError

async def resilient_control():
    max_retries = 3

    for attempt in range(max_retries):
        try:
            async with await Light.from_ip("192.168.1.100") as light:
                await light.set_color(Colors.BLUE)
                print("Success!")
                return

        except LifxTimeoutError:
            print(f"Timeout (attempt {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                await asyncio.sleep(1.0)  # Wait before retry

        except LifxConnectionError as e:
            print(f"Connection failed: {e}")
            break  # Don't retry connection errors

    print("All retries exhausted")
```

### Graceful Degradation

```python
from lifx import discover, DeviceGroup, LifxError

async def best_effort_control():
    devices = []
    async for device in discover():
        devices.append(device)
    group = DeviceGroup(devices)

    results = []

    # Try to control all lights, continue on errors
    for light in group.lights:
        try:
            await light.set_color(Colors.GREEN)
            results.append((light, "success"))
        except LifxError as e:
            results.append((light, f"failed: {e}"))

    # Report results
    for light, status in results:
        label = await light.get_label() if status == "success" else "Unknown"
        print(f"{label}: {status}")
```

## Device Capabilities

### Detecting Capabilities

Light capabilities are automatically populated:

```python
from lifx import Light
from lifx.products.registry import ProductCapability

async def check_capabilities():
    async with await Light.from_ip("192.168.1.100") as light:

        print(f"Product: {light.model}")
        print(f"Capabilities: {light.capabilities}")

        # Check specific capabilities
        if ProductCapability.COLOR in light.capabilities:
            await light.set_color(Colors.BLUE)

        if ProductCapability.MULTIZONE in light.capabilities:
            print("This is a multizone device!")

        if ProductCapability.INFRARED in light.capabilities:
            print("Supports infrared!")
```

### Capability-Based Logic

```python
from lifx import discover, DeviceGroup
from lifx.products.registry import ProductCapability

async def capability_aware_control():
    devices = []
    async for device in discover():
        devices.append(device)
    group = DeviceGroup(devices)

    for device in group.devices:

        # Color devices
        if ProductCapability.COLOR in device.capabilities:
            await device.set_color(Colors.PURPLE)

        # Multizone devices
        if ProductCapability.MULTIZONE in device.capabilities:
            await device.set_color_zones(0, 8, Colors.RED)
```

## Custom Effects

### Creating Smooth Transitions

```python
import asyncio
from lifx import Light, HSBK

async def smooth_color_cycle():
    async with await Light.from_ip("192.168.1.100") as light:
        hues = [0, 60, 120, 180, 240, 300, 360]

        for hue in hues:
            color = HSBK(hue=hue, saturation=1.0, brightness=1.0, kelvin=3500)
            await light.set_color(color, duration=2.0)  # 2 second transition
            await asyncio.sleep(2.0)
```

### Synchronized Multi-Device Effects

```python
import asyncio
from lifx import discover, DeviceGroup, Colors

async def synchronized_flash():
    devices = []
    async for device in discover():
        devices.append(device)
    group = DeviceGroup(devices)

    # Flash all devices simultaneously
    for _ in range(5):
        await group.set_color(Colors.RED, duration=0.0)
        await asyncio.sleep(0.2)
        await group.set_color(Colors.OFF, duration=0.0)
        await asyncio.sleep(0.2)
```

### Wave Effect Across Devices

```python
import asyncio
from lifx import discover, DeviceGroup, Colors

async def wave_effect():
    devices = []
    async for device in discover():
        devices.append(device)
    group = DeviceGroup(devices)

    for i, device in enumerate(group.devices):
        # Each device changes color with a delay
        asyncio.create_task(
            delayed_color_change(device, Colors.BLUE, delay=i * 0.3)
        )

async def delayed_color_change(device, color, delay):
    await asyncio.sleep(delay)
    await device.set_color(color, duration=1.0)
```

## Performance Optimization

### Minimize Network Requests

```python
# ❌ Inefficient: Multiple round-trips
async def inefficient():
    async with await Light.from_ip("192.168.1.100") as light:
        await light.set_power(True)
        await asyncio.sleep(0.1)
        await light.set_color(Colors.BLUE)
        await asyncio.sleep(0.1)
        await light.set_brightness(0.8)

# ✅ Efficient: Set color and brightness together
async def efficient():
    async with await Light.from_ip("192.168.1.100") as light:
        await light.set_power(True)
        # Set color includes brightness
        color = HSBK(hue=240, saturation=1.0, brightness=0.8, kelvin=3500)
        await light.set_color(color, duration=0.0)
```

### Batch Operations

```python
from lifx import discover, DeviceGroup, Colors

# ❌ Sequential: Takes N * latency
async def sequential():
    devices = []
    async for device in discover():
        devices.append(device)
    group = DeviceGroup(devices)

    for device in group.devices:
        await device.set_color(Colors.GREEN)

# ✅ Parallel: Takes ~latency
async def parallel():
    devices = []
    async for device in discover():
        devices.append(device)
    group = DeviceGroup(devices)

    await group.set_color(Colors.GREEN)
```

### Connection Reuse

```python
# ❌ Creates new connection each time
async def no_reuse():
    for _ in range(10):
        async with await Light.from_ip("192.168.1.100") as light:
            await light.set_brightness(0.5)
        # Connection closed here

# ✅ Reuses connection
async def with_reuse():
    async with await Light.from_ip("192.168.1.100") as light:
        for _ in range(10):
            await light.set_brightness(0.5)
        # Connection closed once at end
```

### Fire-and-Forget Mode for High-Frequency Animations

For animations sending more than 20 updates per second, waiting for device acknowledgement creates unacceptable latency. Use the `fast=True` parameter to enable fire-and-forget mode:

```python
import asyncio
from lifx import MultiZoneLight, HSBK

async def rainbow_animation():
    async with await MultiZoneLight.from_ip("192.168.1.100") as light:
        zone_count = await light.get_zone_count()

        # Animation loop at ~30 FPS
        offset = 0
        while True:
            # Generate rainbow colors
            colors = [
                HSBK(hue=(i * 360 / zone_count + offset) % 360,
                     saturation=1.0, brightness=1.0, kelvin=3500)
                for i in range(zone_count)
            ]

            # Fire-and-forget: no waiting for response
            await light.set_extended_color_zones(0, colors, fast=True)

            offset = (offset + 5) % 360
            await asyncio.sleep(0.033)  # ~30 FPS
```

**When to use `fast=True`:**

- High-frequency animations (>20 updates/second)
- Real-time visualizations (music sync, games)
- Smooth color transitions requiring rapid updates

**Trade-offs:**

- No confirmation that the device received or applied the colors
- No error detection (timeouts, unsupported commands)
- Best for visual effects where occasional dropped frames are acceptable

**Note:** `MatrixLight.set64()` is already fire-and-forget by default, making it ideal for tile animations without any additional parameters.

## Next Steps

- [Troubleshooting Guide](troubleshooting.md) - Common issues and solutions
- [Protocol Reference](../api/protocol.md) - Low-level protocol details
- [API Reference](../api/index.md) - Complete API documentation
