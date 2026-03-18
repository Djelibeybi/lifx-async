# Exceptions

lifx-async defines a hierarchy of exceptions for different error conditions. All exceptions inherit from `LifxError`.

## Exception Hierarchy

```text
LifxError (base exception)
├── LifxConnectionError
├── LifxTimeoutError
├── LifxDeviceNotFoundError
├── LifxProtocolError
├── LifxNetworkError
└── LifxUnsupportedCommandError
```

## Base Exception

### LifxError

Bases: `Exception`

Base exception for all lifx-async errors.

## Connection Exceptions

### LifxConnectionError

Bases: `LifxError`

Raised when there's a connection error.

Raised when an operation is attempted on a connection that is not open. Use the `async with` context manager to ensure connections are opened and closed correctly.

### LifxTimeoutError

Bases: `LifxError`

Raised when an operation times out.

Raised by the network transport layer when no data is received within the timeout period, and by the connection layer when a request receives no matching response before the deadline.

### LifxDeviceNotFoundError

Bases: `LifxError`

Raised when a device cannot be found or reached.

Raised by `Device.from_ip()` and `Device.connect()` when the target device does not respond or has an unknown product ID.

## Protocol Exceptions

### LifxProtocolError

Bases: `LifxError`

Raised when there's an error with protocol parsing or validation.

Raised when a packet lacks the required `PKT_TYPE` attribute, when header deserialization fails, or when a response packet type does not match the expected type.

## Network Exceptions

### LifxNetworkError

Bases: `LifxError`

Raised when there's a network-level error.

Raised when the UDP or mDNS socket cannot be opened, when sending or receiving data fails at the OS level, or when the socket is not open.

## Command Exceptions

### LifxUnsupportedCommandError

Bases: `LifxError`

Raised when a device doesn't support the requested command.

Raised when a device returns a `StateUnhandled` response indicating the packet type is not supported, or when calling a method that requires a capability the device does not have.

## Examples

### Basic Exception Handling

```python
from lifx import discover, Colors, LifxError, LifxTimeoutError


async def main():
    try:
        async for device in discover(timeout=5.0):
            await device.set_color(Colors.BLUE)
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
from lifx import discover, LifxError


async def safe_control():
    try:
        async for device in discover():
            await device.set_brightness(0.8)
    except LifxError as e:
        # Catches all LIFX-specific exceptions
        print(f"LIFX operation failed: {e}")
        # Log, retry, or handle gracefully
```

### Timeout Handling

```python
from lifx.network.connection import DeviceConnection
from lifx.exceptions import LifxTimeoutError
from lifx.protocol import packets


async def main():
    try:
        conn = DeviceConnection(serial="d073d5123456", ip="192.168.1.100", timeout=2.0)
        response = await conn.request(packets.Light.Get())
    except LifxTimeoutError:
        print("Device did not respond in time")
        # Device may be offline or unreachable
    finally:
        await conn.close()
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
from lifx import discover, LifxUnsupportedCommandError


async def main():
    async for device in discover():
        try:
            # Some devices may not support all features
            await device.set_infrared(0.5)
        except LifxUnsupportedCommandError:
            print(f"{device.serial} doesn't support this command")
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
light = Light(serial="d073d5123456", ip="192.168.1.100")
try:
    await light.set_color(Colors.BLUE)
except LifxError:
    pass  # Connection not properly managed!
finally:
    await light.connection.close()
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
from lifx import discover, Colors, LifxError


async def main():
    async for device in discover():
        try:
            await device.set_color(Colors.BLUE)
        except LifxError as e:
            # Continue with other devices even if one fails
            print(f"Failed to control {device.serial}: {e}")
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
devices = []
async for device in discover(timeout=3.0):
    devices.append(device)
if not devices:
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
conn = DeviceConnection(serial="d073d5123456", ip="192.168.1.100")
response = await conn.request(packet)
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
