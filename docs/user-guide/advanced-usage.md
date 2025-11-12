# Advanced Usage

This guide covers advanced lifx patterns and techniques for building robust LIFX integrations.

## Table of Contents

- [Storing State](#storing-state)
- [Connection Management](#connection-management)
- [Concurrency Patterns](#concurrency-patterns)
- [Error Handling](#error-handling)
- [Device Capabilities](#device-capabilities)
- [Custom Effects](#custom-effects)
- [Performance Optimization](#performance-optimization)

## Storing State

Device properties return stored state as `(value, timestamp)` tuples, giving you explicit control over data freshness.

lifx-async tries to automatically populate initial state values when a device is used as an async context manager.

Non-state related properties including `version`, `model`, `min_kelvin`, and `max_kelvin` do not return a timestamp.


### Understanding Stored State

All device state properties return timestamped tuples:

```python
from lifx import Light
import time

async def check_stored_state():
    async with await Light.from_ip("192.168.1.100") as light:
        # Property returns tuple with (value, timestamp)
        result = light.label
        if result:
            label_text, timestamp = result
            age = time.time() - timestamp
            print(f"Label: {label_text} (stored {age:.1f}s ago)")
        else:
            print("No stored label - fetching from device")
            label_text = await light.get_label()
            print(f"Label: {label_text}")
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

        # Properties also get updated with new timestamp
        stored_color = light.color  # Now has fresh data
        stored_label = light.label  # Also updated from get_color()
```

### Checking Data Freshness

Determine if stored data is still relevant:

```python
import time

async def use_fresh_or_stored():
    async with await Light.from_ip("192.168.1.100") as light:
        MAX_AGE = 5.0  # Maximum age in seconds

        # Check if we have stored color
        stored = light.color
        if stored:
            color, timestamp = stored
            age = time.time() - timestamp

            if age < MAX_AGE:
                print(f"Using stored color (age: {age:.1f}s)")
            else:
                print("Stored color too old, fetching fresh color")
                # get_color() returns (color, power, label)
                color, _, _ = await light.get_color()
        else:
            print("No stored color, fetching from device")
            # get_color() returns (color, power, label)
            color, _, _ = await light.get_color()
```

### Available Properties

#### Device Properties

- `Device.label` - Device name/label
- `Device.power` - Power state (on/off)
- `Device.version` - Vendor ID and Product ID
- `Device.host_firmware` - Major and minor host firmware version and build number
- `Device.wifi_firmware` - Major and minor wifi firmware version and build number
- `Device.location` - Device location name/label
- `Device.group` - Device group name/label

##### Non-State Properties

- `Device.model` - Device product model

#### Light properties

- `Light.color` - Current color

##### Non-State Properties

- `Light.min_kelvin` - Lowest supported kelvin value
- `Light.max_kelvin` - Highest supported kelvin value

#### InfraredLight properties

- `InfraredLight.infrared` - Infrared brightness

#### HevLight properties:

- `HevLight.hev_cycle` - HEV cycle state
- `HevLight.hev_config` - HEV configuration
- `HevLight.hev_result` - Last HEV result

#### MultiZoneLight properties:

- `MultiZoneLight.zone_count` - Number of zones
- `MultiZoneLight.zone_effect` - Either MOVE or OFF
- `MultiZoneLight.zones` - List of zone colors

#### TileDevice properties:

- `TileDevice.tile_count` - Number of tiles on the chain
- `TileDevice.tile_chain` - Details of each tile on the chain
- `TileDevice.tile_effect` - Either MORPH, FLAME, SKY or OFF
- `TileDevice.tile_colors` - Dictionary of colors, width, and height indexed by tile


All state properties return `None` if no data has been stored yet, or `(value, timestamp)` if data is available.


## Connection Management

### Understanding Connection Pooling

lifx-async automatically pools connections for efficient reuse:

```python
from lifx import Light

async def main():
    async with await Light.from_ip("192.168.1.100") as light:
        # All these operations reuse the same connection
        await light.set_power(True)
        await light.set_color(Colors.BLUE)
        await light.get_label()
        # Connection automatically closed when exiting context
```

**Benefits:**

- Reduced overhead from socket creation/teardown
- Lower latency for repeated operations
- Automatic cleanup on context exit

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
from lifx import discover, Colors

async def multi_device_control():
    async with discover() as group:
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
from lifx import discover, LifxError

async def best_effort_control():
    async with discover() as group:
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
from lifx import discover
from lifx.products.registry import ProductCapability

async def capability_aware_control():
    async with discover() as group:

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
from lifx import discover, Colors

async def synchronized_flash():
    async with discover() as group:
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
from lifx import discover, Colors

async def wave_effect():
    async with discover() as group:
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
# ❌ Sequential: Takes N * latency
async def sequential():
    async with discover() as group:
        for device in group.devices:
            await device.set_color(Colors.GREEN)

# ✅ Parallel: Takes ~latency
async def parallel():
    async with discover() as group:
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

## Next Steps

- [Troubleshooting Guide](troubleshooting.md) - Common issues and solutions
- [Protocol Reference](../api/protocol.md) - Low-level protocol details
- [API Reference](../api/index.md) - Complete API documentation
