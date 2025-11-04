# Advanced Usage

This guide covers advanced lifx patterns and techniques for building robust LIFX integrations.

## Table of Contents

- [Connection Management](#connection-management)
- [Concurrency Patterns](#concurrency-patterns)
- [State Caching](#state-caching)
- [Error Handling](#error-handling)
- [Device Capabilities](#device-capabilities)
- [Custom Effects](#custom-effects)
- [Performance Optimization](#performance-optimization)

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
        label, power, color = await asyncio.gather(
            light.get_label(),
            light.get_power(),
            light.get_color(),
        )

        print(f"{label}: Power={power}, Color={color}")
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

## State Caching

### Cache Configuration

Configure cache TTL per device:

```python
from lifx import Light

# Short cache for frequently changing state
light = Light(
    serial="d073d5000001",
    ip="192.168.1.100",
    cache_ttl=1.0  # 1 second cache
)

# Longer cache for stable metadata
light_stable = Light(
    serial="d073d5000001",
    ip="192.168.1.100",
    cache_ttl=60.0  # 1 minute cache
)
```

### Manual Cache Control

```python
async def cache_management():
    async with await Light.from_ip("192.168.1.100") as light:
        # First call: network request
        color1 = await light.get_color()

        # Second call within TTL: uses cache
        color2 = await light.get_color()  # No network request!

        # Force refresh by invalidating cache
        light.invalidate_cache()
        color3 = await light.get_color()  # Network request
```

### Cache TTL Categories

lifx-async uses different TTLs for different data types:

```python
# Built-in TTL values (in Device class)
STATE_CACHE_TTL = 5.0        # Color, power, zones (changes frequently)
METADATA_CACHE_TTL = 180.0   # Label, version, info (rarely changes)
```

## Error Handling

### Exception Hierarchy

```python
from lifx.exceptions import (
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
from lifx import Light, Colors
from lifx.exceptions import LifxTimeoutError, LifxConnectionError

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
from lifx import discover
from lifx.exceptions import LifxError

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
                await device.set_zone_color(0, 8, Colors.RED)
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

### Cache Warm-Up

```python
async def warm_up_cache():
    async with discover() as group:
        # Pre-fetch frequently accessed data
        await asyncio.gather(
            *[device.get_label() for device in group.devices],
            *[device.get_version() for device in group.devices],
        )

        # Now cached data is available instantly
        for device in group.devices:
            label = await device.get_label()  # From cache
            print(f"Device: {label}")
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
