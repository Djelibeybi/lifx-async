# Exceptions

lifx-async defines a hierarchy of exceptions for different error conditions. All exceptions inherit from
`LifxError`.

## Exception Hierarchy

```
LifxError (base exception)
├── LifxConnectionError
├── LifxTimeoutError
├── LifxDeviceNotFoundError
├── LifxProtocolError
├── LifxNetworkError
└── LifxUnsupportedCommandError
```

## Base Exception

::: lifx.exceptions.LifxError
    options:
      show_root_heading: true
      heading_level: 3
      members_order: source

## Connection Exceptions

::: lifx.exceptions.LifxConnectionError
    options:
      show_root_heading: true
      heading_level: 3
      members_order: source

::: lifx.exceptions.LifxTimeoutError
    options:
      show_root_heading: true
      heading_level: 3
      members_order: source

::: lifx.exceptions.LifxDeviceNotFoundError
    options:
      show_root_heading: true
      heading_level: 3
      members_order: source

## Protocol Exceptions

::: lifx.exceptions.LifxProtocolError
    options:
      show_root_heading: true
      heading_level: 3
      members_order: source

## Network Exceptions

::: lifx.exceptions.LifxNetworkError
    options:
      show_root_heading: true
      heading_level: 3
      members_order: source

## Command Exceptions

::: lifx.exceptions.LifxUnsupportedCommandError
    options:
      show_root_heading: true
      heading_level: 3
      members_order: source

## Examples

### Basic Exception Handling

```python
from lifx import discover, LifxError, LifxTimeoutError


async def main():
    try:
        async with discover(timeout=5.0) as group:
            await group.set_color(Colors.BLUE)
    except LifxTimeoutError:
        print("Discovery timed out - no devices found")
    except LifxError as e:
        print(f"LIFX error: {e}")
```

### Specific Exception Handling

```python
from lifx import Light, LifxConnectionError, LifxUnsupportedCommandError


async def main():
    try:
        async with await Light.from_ip("192.168.1.100") as light:
            await light.set_color(Colors.BLUE)
    except LifxConnectionError:
        print("Failed to connect to device")
    except LifxUnsupportedCommandError as e:
        print(f"Device doesn't support this operation: {e}")
```

### Catching All LIFX Exceptions

```python
from lifx import find_lights, LifxError


async def safe_control():
    try:
        async with find_lights() as lights:
            for light in lights:
                await light.set_brightness(0.8)
    except LifxError as e:
        # Catches all LIFX-specific exceptions
        print(f"LIFX operation failed: {e}")
        # Log, retry, or handle gracefully
```

### Timeout Handling

```python
from lifx import DeviceConnection, LifxTimeoutError
from lifx.protocol.packets import LightGet, LightState


async def main():
    try:
        async with DeviceConnection(serial, ip, timeout=2.0) as conn:
            response = await conn.request_response(LightGet(), LightState)
    except LifxTimeoutError:
        print("Device did not respond in time")
        # Device may be offline or unreachable
```

### Protocol Error Handling

```python
from lifx import Light, LifxProtocolError


async def main():
    try:
        async with await Light.from_ip("192.168.1.100") as light:
            await light.set_color(Colors.BLUE)
    except LifxProtocolError:
        print("Protocol-level error occurred")
```

### Unsupported Command Handling

```python
from lifx import find_lights, LifxUnsupportedCommandError


async def main():
    async with find_lights() as lights:
        for light in lights:
            try:
                # Some devices may not support all features
                await light.set_infrared(0.5)
            except LifxUnsupportedCommandError:
                print(f"{light.label} doesn't support this command")
                continue
```

### Device Not Found Handling

```python
from lifx import find_by_serial, LifxDeviceNotFoundError


async def main():
    try:
        device = await find_by_serial("d073d5123456", timeout=3.0)
        if device:
            async with device:
                await device.set_power(True)
    except LifxDeviceNotFoundError:
        print("Device not found on the network")
```

## Best Practices

### Always Catch Specific Exceptions First

```python
# ✅ Good - specific to general
try:
    await light.set_color(Colors.BLUE)
except LifxTimeoutError:
    print("Timeout")
except LifxConnectionError:
    print("Connection failed")
except LifxError:
    print("Other LIFX error")

# ❌ Bad - general exception catches everything
try:
    await light.set_color(Colors.BLUE)
except LifxError:
    print("Error")  # Can't distinguish timeout from other errors
```

### Use Context Managers for Cleanup

```python
# ✅ Good - resources cleaned up even on exception
try:
    async with await Light.from_ip(ip) as light:
        await light.set_color(Colors.BLUE)
except LifxError:
    print("Error occurred but connection was closed properly")

# ❌ Bad - connection may leak on exception
light = Light(serial, ip)
await light.connect()
try:
    await light.set_color(Colors.BLUE)
except LifxError:
    pass  # Connection not closed!
finally:
    await light.disconnect()
```

### Log Exceptions for Debugging

```python
import logging
from lifx import discover, DeviceGroup, LifxError

logger = logging.getLogger(__name__)


async def main():
    try:
        devices = []
        async for device in discover():
            devices.append(device)
        group = DeviceGroup(devices)
        await group.set_color(Colors.BLUE)
    except LifxError as e:
        logger.exception("Failed to control lights")
        # Logs full traceback for debugging
```

### Graceful Degradation

```python
from lifx import find_lights, LifxError


async def main():
    async with find_lights() as lights:
        for light in lights:
            try:
                await light.set_color(Colors.BLUE)
            except LifxError as e:
                # Continue with other lights even if one fails
                print(f"Failed to control {light.label}: {e}")
                continue
```

## Common Error Scenarios

### Device Not Responding

```python
# Usually raises: LifxTimeoutError
async with await Light.from_ip("192.168.1.100", timeout=5.0) as light:
    await light.set_color(Colors.BLUE)
```

Causes:

- Device is offline or unpowered
- Wrong IP address
- Network connectivity issues
- Firewall blocking UDP port 56700

### Device Not Found During Discovery

```python
# May raise: LifxTimeoutError or LifxDeviceNotFoundError
async with discover(timeout=3.0) as group:
    if not group.devices:
        print("No devices found")
```

Causes:

- No LIFX devices on the network
- Devices on different subnet
- Discovery timeout too short
- Network doesn't allow broadcast packets

### Connection Failed

```python
# Raises: LifxConnectionError
async with DeviceConnection(serial, ip) as conn:
    await conn.send_packet(packet)
```

Causes:

- Network unreachable
- Device offline
- Port blocked by firewall
- Invalid IP address

### Unsupported Command

```python
# Raises: LifxUnsupportedCommandError
async with await Light.from_ip(ip) as light:
    await light.set_color_zones(0, 5, Colors.RED)  # Not a multizone device
```

Causes:

- Attempting zone control on non-multizone device
- Using tile operations on non-tile device
- Feature not supported by firmware version
- Sending Light commands to non-light devices (e.g., switches)

### Protocol Error

```python
# Raises: LifxProtocolError
```

Causes:

- Invalid packet format received
- Protocol parsing failure
- Corrupted message data
- Unexpected packet type
